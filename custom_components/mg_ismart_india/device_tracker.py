from __future__ import annotations

from homeassistant.components.device_tracker import SourceType, TrackerEntity

from .const import DOMAIN
from .entity import MgIndiaEntity


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([MgTracker(hass.data[DOMAIN][entry.entry_id]["coordinator"])])


class MgTracker(MgIndiaEntity, TrackerEntity):
    _attr_source_type = SourceType.GPS

    def __init__(self, coordinator):
        super().__init__(coordinator, "location", "Location")

    @property
    def _fix(self):
        gps = self.status.gps if self.status else None
        return gps if gps and gps.has_fix else None

    @property
    def latitude(self):
        return self._fix.latitude if self._fix else None

    @property
    def longitude(self):
        return self._fix.longitude if self._fix else None

    @property
    def extra_state_attributes(self):
        gps = self._fix
        return {
            "heading_deg": gps.heading_deg if gps else None,
            "altitude_m": gps.altitude_m if gps else None,
        }
