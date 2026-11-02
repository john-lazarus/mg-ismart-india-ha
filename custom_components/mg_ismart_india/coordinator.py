from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import timedelta
import logging
from typing import TypeVar

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from aiohttp import ClientError
from mg_ismart_india_client import (
    MgIndiaApiError,
    MgIndiaClient,
    MgIndiaLoginRejected,
    Snapshot,
)

from .const import DEFAULT_SCAN_INTERVAL_SECONDS, DOMAIN

_LOGGER = logging.getLogger(__name__)
_T = TypeVar("_T")


def _vehicle_config(vehicle, code: str, default=None):
    raw = getattr(vehicle, "raw", None)
    if isinstance(raw, dict):
        for block_name in ("configuration", "config", "modelConfig"):
            block = raw.get(block_name)
            if isinstance(block, dict) and code in block:
                return block[code]
        for item in raw.get("vehicleModelConfiguration", []) or []:
            if isinstance(item, dict) and item.get("itemCode") == code:
                return item.get("itemValue", default)
    return default


def is_electric(vehicle) -> bool:
    text = " ".join(
        str(value or "")
        for value in (
            getattr(vehicle, "name", None),
            getattr(vehicle, "model", None),
            getattr(vehicle, "brand", None),
            _vehicle_config(vehicle, "EV"),
            _vehicle_config(vehicle, "BType"),
        )
    ).lower()
    if str(_vehicle_config(vehicle, "EV", "")).strip() == "1":
        return True
    if str(_vehicle_config(vehicle, "BType", "")).strip() == "1":
        return True
    return any(token in text for token in ("electric", " ev", "comet", "windsor"))


class MgIndiaCoordinator(DataUpdateCoordinator):
    def __init__(self, hass: HomeAssistant, client: MgIndiaClient):
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL_SECONDS),
        )
        self.client = client
        self._command_lock = asyncio.Lock()
        self.command_in_progress = False
        self.command_name: str | None = None
        self.last_command_status: str | None = None
        self.last_command_error: str | None = None

    async def _async_update_data(self):
        c = self.client
        if not c.vehicle or c.vehicle.vin != c.vin:
            await c.vehicles()
        vehicle = c.vehicle
        if not is_electric(vehicle):
            return await c.snapshot()
        # Same as client.snapshot(), but the single status poll also asks for
        # the charging frame (status.charge stays None when none arrives).
        caps = await c.refresh_capabilities()
        try:
            status = await c.status(include_charge=True)
        except MgIndiaLoginRejected:
            raise
        except (ClientError, TimeoutError, MgIndiaApiError) as err:
            _LOGGER.warning("EV charge poll failed, using status only: %s", err)
            status = await c.status()
        if c.vin != vehicle.vin:
            raise MgIndiaApiError("VIN changed during snapshot")
        return Snapshot(vehicle, caps, status)

    async def async_run_command(
        self, name: str, operation: Callable[[], Awaitable[_T]]
    ) -> _T:
        if self._command_lock.locked():
            raise HomeAssistantError(
                f"Another MG remote command is already running: {self.command_name}"
            )
        async with self._command_lock:
            self.command_in_progress = True
            self.command_name = name
            self.last_command_status = "processing"
            self.last_command_error = None
            self.async_update_listeners()
            try:
                result = await operation()
                self.last_command_status = "refreshing"
                self.async_update_listeners()
                await self.async_request_refresh()
                self.last_command_status = "success"
                return result
            except Exception as err:
                self.last_command_status = "failed"
                self.last_command_error = str(err)
                raise
            finally:
                self.command_in_progress = False
                self.async_update_listeners()
