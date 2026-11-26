from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
import logging
from typing import TypeVar

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from aiohttp import ClientError
from mg_ismart_india_client import (
    MgIndiaApiError,
    MgIndiaClient,
    MgIndiaLoginRejected,
    MgIndiaVehicleUnreachable,
    Snapshot,
)

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
_T = TypeVar("_T")


class MgIndiaCoordinator(DataUpdateCoordinator):
    def __init__(
        self,
        hass: HomeAssistant,
        client: MgIndiaClient,
        vin: str | None,
        pin_hash: str | None,
        parked_min: int,
        active_min: int,
    ):
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=parked_min),
        )
        self.client = client
        self.vin = vin
        self.pin_hash = pin_hash
        self.parked_min = parked_min
        self.active_min = active_min
        self.last_update: datetime | None = None
        self._command_lock = asyncio.Lock()
        self.command_in_progress = False
        self.command_name: str | None = None
        self.last_command_status: str | None = None
        self.last_command_error: str | None = None

    @property
    def has_pin(self) -> bool:
        return bool(self.pin_hash)

    async def _async_update_data(self):
        try:
            async with self.client.for_vehicle(self.vin, self.pin_hash) as c:
                snap = await self._fetch(c)
        except MgIndiaLoginRejected:
            raise
        except (MgIndiaApiError, ClientError, TimeoutError) as err:
            raise UpdateFailed(str(err) or type(err).__name__) from err
        s = snap.status
        # A status poll wakes the car (CAN reads on), so CAN activity is not "active".
        active = (s.charge and s.charge.is_charging) or s.climate_running or s.is_moving
        self.update_interval = timedelta(
            minutes=self.active_min if active else self.parked_min
        )
        self.last_update = datetime.now(UTC)
        return snap

    async def _fetch(self, c: MgIndiaClient):
        if not c.vehicle or c.vehicle.vin != c.vin:
            await c.vehicles()
        vehicle = c.vehicle
        if not vehicle.is_electric:
            return await c.snapshot()
        # Same as client.snapshot(), but the single status poll also asks for
        # the charging frame (status.charge stays None when none arrives).
        caps = await c.refresh_capabilities()
        try:
            status = await c.status(include_charge=True)
        except (MgIndiaLoginRejected, MgIndiaVehicleUnreachable):
            # A car that didn't answer the status request would only be woken again.
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
                async with self.client.for_vehicle(self.vin, self.pin_hash):
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
