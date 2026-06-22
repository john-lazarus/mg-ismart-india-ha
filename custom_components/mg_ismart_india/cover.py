from __future__ import annotations

from homeassistant.components.cover import (
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)

from .const import DOMAIN
from .entity import MgIndiaEntity


async def async_setup_entry(hass, entry, async_add_entities):
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    entities = []
    caps = coordinator.data.capabilities if coordinator.data else None
    if caps and caps.window_param_ids:
        entities.append(MgWindows(coordinator, data["client"]))
    if caps and caps.sunroof:
        entities.append(MgSunroof(coordinator, data["client"]))
    async_add_entities(entities)


class _Base(MgIndiaEntity, CoverEntity):
    _attr_supported_features = CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE

    def __init__(self, coordinator, key, name, client):
        super().__init__(coordinator, key, name)
        self.client = client

    @property
    def available(self):
        return (
            super().available
            and self.client.has_pin
            and not getattr(self.coordinator, "command_in_progress", False)
        )


class MgWindows(_Base):
    _attr_device_class = CoverDeviceClass.WINDOW

    def __init__(self, coordinator, client):
        super().__init__(coordinator, "windows_control", "Windows", client)

    @property
    def is_closed(self):
        if not self.status or not self.caps:
            return None
        values = {
            9: self.status.driver_window_open,
            10: self.status.passenger_window_open,
            11: self.status.rear_left_window_open,
            12: self.status.rear_right_window_open,
        }
        chosen = [values.get(item) for item in self.caps.window_param_ids]
        return None if not chosen else not any(v for v in chosen if v is not None)

    async def async_open_cover(self, **kwargs):
        await self.coordinator.async_run_command(
            "Open windows",
            lambda: self.client.control_windows(True, self.caps.window_param_ids),
        )

    async def async_close_cover(self, **kwargs):
        await self.coordinator.async_run_command(
            "Close windows",
            lambda: self.client.control_windows(False, self.caps.window_param_ids),
        )


class MgSunroof(_Base):
    _attr_device_class = CoverDeviceClass.WINDOW

    def __init__(self, coordinator, client):
        super().__init__(coordinator, "sunroof_control", "Sunroof", client)

    @property
    def is_closed(self):
        if not self.status or self.status.sunroof_open is None:
            return None
        return not self.status.sunroof_open

    async def async_open_cover(self, **kwargs):
        await self.coordinator.async_run_command(
            "Open sunroof", lambda: self.client.control_sunroof(True)
        )

    async def async_close_cover(self, **kwargs):
        await self.coordinator.async_run_command(
            "Close sunroof", lambda: self.client.control_sunroof(False)
        )
