import asyncio
import types
from datetime import timedelta

from custom_components.mg_ismart_india import async_setup_entry, async_unload_entry
from custom_components.mg_ismart_india.config_flow import options_from_user_input
from custom_components.mg_ismart_india.coordinator import MgIndiaCoordinator
from mg_ismart_india_client import (
    Capabilities,
    GpsPosition,
    GpsStatus,
    MgIndiaApiError,
    MgIndiaClient,
    Snapshot,
    Status,
    Vehicle,
)


def test_interval_parked_vs_active():
    async def run():
        status = Status()
        coord = MgIndiaCoordinator(None, MgIndiaClient(None, "9876543210", "pw"), "V", None, 30, 5)

        async def fake(c):
            return Snapshot(Vehicle("V", "Car"), Capabilities(), status)

        coord._fetch = fake
        await coord._async_update_data()
        assert coord.update_interval == timedelta(minutes=30)
        assert coord.last_update.tzinfo is not None
        status.can_bus_active = True
        await coord._async_update_data()
        assert coord.update_interval == timedelta(minutes=30)
        status.gps = GpsPosition(latitude=1.0, longitude=2.0, speed_kmh=40.0, gps_status=GpsStatus.FIX_3D)
        await coord._async_update_data()
        assert coord.update_interval == timedelta(minutes=5)
        status.gps = None
        status.climate_running = True
        await coord._async_update_data()
        assert coord.update_interval == timedelta(minutes=5)

    asyncio.run(run())


def test_two_entries_share_one_account_client(monkeypatch):
    async def run():
        import custom_components.mg_ismart_india as mod

        seen = []

        async def fake_fetch(self, c):
            assert c._lock.locked()  # inside for_vehicle()
            seen.append((c.vin, c.pin_hash))
            return Snapshot(Vehicle(c.vin, "Car"), Capabilities(), Status())

        monkeypatch.setattr(MgIndiaCoordinator, "_fetch", fake_fetch)
        monkeypatch.setattr(mod, "async_get_clientsession", lambda hass: None)

        async def ok(*a, **k):
            return True

        hass = types.SimpleNamespace(
            data={},
            config_entries=types.SimpleNamespace(
                async_forward_entry_setups=ok, async_unload_platforms=ok
            ),
        )

        def entry(eid, vin, pin):
            return types.SimpleNamespace(
                entry_id=eid,
                data={"phone": "+91 98765 43210", "password": "pw", "vin": vin, "pin_hash": pin},
                options={},
                async_on_unload=lambda cb: None,
                add_update_listener=lambda cb: None,
            )

        a, b = entry("a", "VIN_A", "pa"), entry("b", "VIN_B", None)
        # Skip HA's first-refresh plumbing: run the real update path directly.
        async def first(self):
            await self._async_update_data()

        monkeypatch.setattr(MgIndiaCoordinator, "async_config_entry_first_refresh", first)
        await async_setup_entry(hass, a)
        await async_setup_entry(hass, b)
        accounts = hass.data["mg_ismart_india"]["accounts"]
        assert len(accounts) == 1
        ca = hass.data["mg_ismart_india"]["a"]["coordinator"]
        cb = hass.data["mg_ismart_india"]["b"]["coordinator"]
        assert ca.client is cb.client
        assert seen == [("VIN_A", "pa"), ("VIN_B", None)]
        assert ca.has_pin and not cb.has_pin
        await async_unload_entry(hass, a)
        assert len(accounts) == 1
        await async_unload_entry(hass, b)
        assert accounts == {}

    asyncio.run(run())


def test_options_pass_intervals_and_keep_pin_behaviour():
    iv = {"scan_interval_parked": 60, "scan_interval_active": 2}
    assert options_from_user_input(iv) == iv
    assert options_from_user_input({**iv, "clear_pin": True, "pin": "1234"}) == {
        **iv,
        "pin_hash": "",
    }
    assert len(options_from_user_input({"pin": "1234"})["pin_hash"]) == 32


def test_failed_first_refresh_leaves_no_account_record(monkeypatch):
    import pytest

    import custom_components.mg_ismart_india as mod

    async def boom(self):
        raise RuntimeError("login failed")

    monkeypatch.setattr(MgIndiaCoordinator, "async_config_entry_first_refresh", boom)
    monkeypatch.setattr(mod, "async_get_clientsession", lambda hass: None)
    hass = types.SimpleNamespace(data={})
    e = types.SimpleNamespace(
        entry_id="a",
        data={"phone": "+91 98765 43210", "password": "pw", "vin": "V", "pin_hash": None},
        options={},
    )
    with pytest.raises(RuntimeError):
        asyncio.run(async_setup_entry(hass, e))
    assert hass.data["mg_ismart_india"]["accounts"] == {}


def test_unanswered_first_refresh_retries_once_at_parked_interval(monkeypatch):
    import pytest
    from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady

    import custom_components.mg_ismart_india as mod

    async def no_answer(self):
        raise ConfigEntryNotReady() from MgIndiaApiError("no answer")

    scheduled, cancelled = [], []

    def call_later(hass, delay, cb):
        scheduled.append(delay)
        return lambda: cancelled.append(delay)

    monkeypatch.setattr(MgIndiaCoordinator, "async_config_entry_first_refresh", no_answer)
    monkeypatch.setattr(mod, "async_get_clientsession", lambda hass: None)
    monkeypatch.setattr(mod, "async_call_later", call_later)
    hass = types.SimpleNamespace(data={})
    e = types.SimpleNamespace(
        entry_id="a",
        title="Car",
        data={"phone": "9876543210", "password": "pw", "vin": "V", "pin_hash": None},
        options={"scan_interval_parked": 30},
    )
    with pytest.raises(ConfigEntryError, match="retrying in 30 minutes"):
        asyncio.run(async_setup_entry(hass, e))
    assert scheduled == [1800] and cancelled == []
    with pytest.raises(ConfigEntryError):
        asyncio.run(async_setup_entry(hass, e))
    assert scheduled == [1800, 1800] and cancelled == [1800]
