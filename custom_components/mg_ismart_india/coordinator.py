from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import timedelta
import logging
from typing import TypeVar

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .api import MgIndiaClient
from .const import DEFAULT_SCAN_INTERVAL_SECONDS, DOMAIN

_LOGGER = logging.getLogger(__name__)
_T = TypeVar("_T")


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
        return await self.client.snapshot()

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
