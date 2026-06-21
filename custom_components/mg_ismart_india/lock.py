from __future__ import annotations

from homeassistant.components.lock import LockEntity

from .const import DOMAIN
from .entity import MgIndiaEntity


async def async_setup_entry(hass, entry, async_add_entities):
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    if coordinator.data.capabilities.door_lock:
        async_add_entities([MgDoorLock(coordinator, data["client"])])


class MgDoorLock(MgIndiaEntity, LockEntity):
    def __init__(self, coordinator, client):
        super().__init__(coordinator, "door_lock_control", "Door Lock")
        self.client = client

    @property
    def available(self):
        return super().available and self.client.has_pin

    @property
    def is_locked(self):
        return self.status.locked if self.status else None

    async def async_lock(self, **kwargs):
        await self.client.control_door_lock(True)
        await self.coordinator.async_request_refresh()

    async def async_unlock(self, **kwargs):
        await self.client.control_door_lock(False)
        await self.coordinator.async_request_refresh()
