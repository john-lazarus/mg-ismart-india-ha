from __future__ import annotations

from homeassistant.components.lock import LockEntity

from .const import DOMAIN
from .entity import MgIndiaEntity


async def async_setup_entry(hass, entry, async_add_entities):
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    async_add_entities([MgDoorLock(coordinator, data["client"])])


class MgDoorLock(MgIndiaEntity, LockEntity):
    def __init__(self, coordinator, client):
        super().__init__(coordinator, "door_lock_control", "Door Lock")
        self.client = client

    @property
    def available(self):
        return (
            super().available
            and self.client.has_pin
            and not getattr(self.coordinator, "command_in_progress", False)
        )

    @property
    def is_locked(self):
        return self.status.locked if self.status else None

    async def async_lock(self, **kwargs):
        await self.coordinator.async_run_command(
            "Lock doors", lambda: self.client.control_door_lock(True)
        )

    async def async_unlock(self, **kwargs):
        await self.coordinator.async_run_command(
            "Unlock doors", lambda: self.client.control_door_lock(False)
        )
