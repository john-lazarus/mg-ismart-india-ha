from __future__ import annotations
import asyncio
import hashlib
import json
import re
import time
from typing import Any
from aiohttp import ClientSession
from .crypto import MgIndiaApiError, decrypt_gateway_body, gateway_signature, make_device_id, normalize_phone, tap_signature
from .models import Capabilities, Snapshot, Status, Vehicle
from .tap import decode_control_response, decode_status_response, encode_control_request, encode_pin_request, encode_status_request

TAP_LOGIN_URL = "https://iov-tap.mgindia.co.in/TAP.Web/ota.mp"
TAP_STATUS_URL = "https://iov-tap.mgindia.co.in/TAP.Web/ota.mpv21"
GATEWAY_BASE = "https://iov-gateway.mgindia.co.in/api.app/v1"
LOGIN_PREFIX = "00" * 48
CONTROL_ATTEMPTS = 8
CONTROL_DELAY = 2.0


def _as_list(data: Any) -> list[Any]:
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("list", "vehicleList", "vehicles", "data", "result"):
            if isinstance(data.get(key), list):
                return data[key]
    return []


def _bool(v: Any) -> bool | None:
    if isinstance(v, bool):
        return v
    if isinstance(v, int) and v in (0, 1):
        return bool(v)
    return None


def _int(v: Any, minv: int | None = None,
         maxv: int | None = None) -> int | None:
    try:
        i = int(v)
    except Exception:
        return None
    if minv is not None and i < minv:
        return None
    if maxv is not None and i > maxv:
        return None
    return i


def parse_vehicle(raw: dict[str, Any]) -> Vehicle:
    vin = raw.get("vin") or raw.get("VIN") or raw.get(
        "vinNo") or raw.get("vehicleVin")
    if not vin:
        raise MgIndiaApiError("Vehicle response did not include a VIN")
    name = raw.get("series") or raw.get(
        "modelName") or raw.get("brandName") or str(vin)[-6:]
    return Vehicle(str(vin), str(name), raw.get("brandName"), raw.get(
        "modelName") or raw.get("series"), str(raw.get("modelYear") or "") or None, raw)


def parse_status(raw: dict[str, Any]) -> Status:
    basic = raw.get("basicVehicleStatus", raw)
    bv = _int(basic.get("batteryVoltage"))
    return Status(
        status_time=_int(
            raw.get("statusTime")), locked=_bool(
            basic.get("lockStatus")), driver_door_open=_bool(
                basic.get("driverDoor")), passenger_door_open=_bool(
                    basic.get("passengerDoor")), rear_left_door_open=_bool(
                        basic.get("rearLeftDoor")), rear_right_door_open=_bool(
                            basic.get("rearRightDoor")), boot_open=_bool(
                                basic.get("bootStatus")), bonnet_open=_bool(
                                    basic.get("bonnetStatus")), driver_window_open=_bool(
                                        basic.get("driverWindow")), passenger_window_open=_bool(
                                            basic.get("passengerWindow")), rear_left_window_open=_bool(
                                                basic.get("rearLeftWindow")), rear_right_window_open=_bool(
                                                    basic.get("rearRightWindow")), sunroof_open=_bool(
                                                        basic.get("sunroofStatus")), climate_running=(
                                                            basic.get("remoteClimateStatus") in (
                                                                2, 3)) if basic.get("remoteClimateStatus") is not None else None, interior_temperature=_int(
                                                                    basic.get("interiorTemperature"), -60, 90), exterior_temperature=_int(
                                                                        basic.get("exteriorTemperature"), -60, 90), fuel_level=_int(
                                                                            basic.get("fuelLevelPrc"), 0, 100), range_km=_int(
                                                                                basic.get("fuelRange")), odometer_km=_int(
                                                                                    basic.get("mileage")), aux_battery_voltage=(
                                                                                        bv / 10 if bv is not None else None), can_bus_active=_bool(
                                                                                            basic.get("canBusActive")), last_can_activity=_int(
                                                                                                basic.get("timeOfLastCANBUSActivity")), handbrake=_bool(
                                                                                                    basic.get("handBrake")), raw=raw)


def discover_capabilities(payloads: list[dict[str, Any]]) -> Capabilities:
    cfg: dict[str, Any] = {}
    feature_ids: set[int] = set()
    for p in payloads:
        if not isinstance(p, dict):
            continue
        for block in (
                p.get("configuration"),
                p.get("config"),
                p.get("modelConfig")):
            if isinstance(block, dict):
                cfg.update(block)
        for item in _as_list(p):
            if isinstance(item, dict):
                try:
                    feature_ids.add(
                        int(item.get("featureId") or item.get("id")))
                except Exception:
                    pass

    def enabled(x): return str(x or "").upper() in {
        "1", "Y", "YES", "TRUE", "ON", "SUPPORTED"}
    remote = enabled(cfg.get("S61")) or bool(feature_ids)
    mask = str(cfg.get("WINDOW") or "")
    windows = tuple(
        pid for flag, pid in zip(
            mask, (9, 10, 11, 12), strict=False) if flag.upper() in {
            "1", "Y", "T"})
    return Capabilities(
        climate=enabled(
            cfg.get("T11")) or 2 in feature_ids,
        door_lock=remote,
        find_my_car=remote,
        tailgate=remote and enabled(
            cfg.get("BOOT")),
        sunroof=remote and enabled(
            cfg.get("S35")),
        heated_seats=remote and enabled(
            cfg.get("HeatedSeat")),
        window_param_ids=windows if remote else ())


class MgIndiaClient:
    def __init__(
            self,
            session: ClientSession,
            phone: str,
            password: str,
            vin: str | None = None,
            pin_hash: str | None = None) -> None:
        self.session = session
        self.phone = normalize_phone(phone)
        self.password = password
        self.vin = vin
        self.pin_hash = pin_hash
        self.device_id = make_device_id(self.phone)
        self.uid: str | None = None
        self.token: str | None = None
        self.vehicle: Vehicle | None = None
        self.capabilities = Capabilities()
        self._event = 1

    @property
    def has_pin(self) -> bool: return bool(self.pin_hash)

    def _next_event(self) -> int:
        self._event = (self._event + 1) & 0x7fffffff
        return self._event

    async def login(self) -> None:
        app = f"{
            self.phone}|{
            self.password}|{
            self.device_id}".encode().hex().upper()
        body = LOGIN_PREFIX + app
        async with self.session.post(TAP_LOGIN_URL, data=body, headers={"Content-Type": "application/octet-stream", "APP-SIGNATURE": tap_signature(body)}, timeout=30) as r:
            text = await r.text()
            if r.status >= 400:
                raise MgIndiaApiError(f"Login failed: HTTP {r.status}")
        m = re.search(r"[A-Fa-f0-9]{40}", text)
        if not m:
            raise MgIndiaApiError(
                "Login response did not include a session token")
        self.token = m.group(0).upper()
        self.uid = hashlib.sha1(
            (self.phone + self.token).encode()).hexdigest()[:50]

    async def gateway_get(self,
                          path: str,
                          params: dict[str,
                                       Any] | None = None) -> dict[str,
                                                                   Any]:
        if not self.token:
            await self.login()
        ts = str(int(time.time() * 1000))
        headers = {"Content-Type": "application/json",
                   "APP-TIMESTAMP": ts,
                   "APP-VERIFICATION-STRING": gateway_signature(path,
                                                                ts),
                   "Authorization": self.token or ""}
        async with self.session.get(GATEWAY_BASE + path, params=params, headers=headers, timeout=30) as r:
            text = await r.text()
            hdr = r.headers
            if r.status >= 400:
                raise MgIndiaApiError(
                    f"Gateway {path} failed: HTTP {
                        r.status}")
        try:
            return json.loads(text)
        except Exception:
            return json.loads(decrypt_gateway_body(text, hdr))

    async def vehicles(self) -> list[Vehicle]:
        data = await self.gateway_get("/vehicle/userVinList")
        vehicles = [parse_vehicle(x)
                    for x in _as_list(data) if isinstance(x, dict)]
        if self.vin:
            self.vehicle = next(
                (v for v in vehicles if v.vin == self.vin),
                vehicles[0] if vehicles else None)
        elif vehicles:
            self.vehicle = vehicles[0]
            self.vin = self.vehicle.vin
        return vehicles

    async def refresh_capabilities(self) -> Capabilities:
        if not self.vin:
            await self.vehicles()
        payloads = []
        for path in (
            "/vehicle/feature/list",
            "/vehicle/service/subscription",
            "/navi/vehicle/co2info",
                "/navi/vehicle/co2info/supplementInfo"):
            try:
                payloads.append(await self.gateway_get(path, {"vin": self.vin}))
            except Exception:
                pass
        self.capabilities = discover_capabilities(payloads)
        return self.capabilities

    async def status(self) -> Status:
        if not self.token:
            await self.login()
        if not self.vin:
            await self.vehicles()
        body = encode_status_request(
            self.uid or "0" * 50,
            self.token or "0" * 40,
            self.vin or "",
            self._next_event())
        async with self.session.post(TAP_STATUS_URL, data=body, headers={"Content-Type": "application/octet-stream", "APP-SIGNATURE": tap_signature(body)}, timeout=30) as r:
            text = await r.text()
            if r.status >= 400:
                raise MgIndiaApiError(f"Status failed: HTTP {r.status}")
        _, payload = decode_status_response(text)
        if not payload:
            raise MgIndiaApiError("Empty status response")
        return parse_status(payload)

    async def snapshot(self) -> Snapshot:
        if not self.vehicle:
            await self.vehicles()
        caps = await self.refresh_capabilities()
        status = await self.status()
        return Snapshot(
            self.vehicle or Vehicle(
                self.vin or "unknown",
                self.vin or "unknown"),
            caps,
            status)

    async def verify_pin(self) -> None:
        if not self.pin_hash:
            raise MgIndiaApiError("Control PIN is not configured")
        body = encode_pin_request(
            self.uid or "0" * 50,
            self.token or "0" * 40,
            self.vin or "",
            self._next_event(),
            self.pin_hash)
        async with self.session.post(TAP_STATUS_URL, data=body, headers={"Content-Type": "application/octet-stream", "APP-SIGNATURE": tap_signature(body)}, timeout=30) as r:
            if r.status >= 400:
                raise MgIndiaApiError(
                    f"PIN verification failed: HTTP {
                        r.status}")

    async def _control(self, name: str, typ: int,
                       params: list[tuple[int, bytes]]) -> None:
        await self.verify_pin()
        for attempt in range(8):
            body = encode_control_request(
                self.uid or "0" * 50,
                self.token or "0" * 40,
                self.vin or "",
                self._next_event(),
                typ,
                params)
            async with self.session.post(TAP_STATUS_URL, data=body, headers={"Content-Type": "application/octet-stream", "APP-SIGNATURE": tap_signature(body)}, timeout=30) as r:
                text = await r.text()
                if r.status >= 400:
                    raise MgIndiaApiError(f"{name} failed: HTTP {r.status}")
            _, ctrl = decode_control_response(text)
            if ctrl and ctrl.get("rvcReqSts") == b"\x02":
                return
            if attempt < 7:
                await asyncio.sleep(CONTROL_DELAY)
        raise MgIndiaApiError(f"{name} did not complete")

    async def control_climate(self,
                              on: bool) -> None: await self._control("Climate",
                                                                     6,
                                                                     [(1,
                                                                       b"\x01" if on else b"\x00")])

    async def control_door_lock(
        self, lock: bool) -> None: await self._control(
        "Door lock", 1 if lock else 2, [
            (1, b"\x01" if lock else b"\x00")])

    async def find_my_car(
        self) -> None: await self._control("Find my car", 5, [(1, b"\x01")])

    async def release_tailgate(
        self) -> None: await self._control("Tailgate", 7, [(1, b"\x01")])

    async def control_windows(self,
                              open_windows: bool,
                              ids: tuple[int,
                                         ...]) -> None: await self._control("Windows",
                                                                            3,
                                                                            [(i,
                                                                              b"\x03" if open_windows else b"\x00") for i in ids] + [(13,
                                                                                                                                      b"\x03" if open_windows else b"\x00")])

    async def control_sunroof(
        self, open_sunroof: bool) -> None: await self._control(
        "Sunroof", 3, [
            (13, b"\x03" if open_sunroof else b"\x00")])

    async def control_heated_seats(
        self, driver: int, passenger: int) -> None: await self._control(
        "Heated seats", 8, [
            (20, bytes(
                [driver])), (21, bytes(
                    [passenger]))])
