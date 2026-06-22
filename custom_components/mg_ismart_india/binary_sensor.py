from __future__ import annotations
from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorDeviceClass,
)
from .const import DOMAIN
from .entity import MgIndiaEntity

BINS = [
    ("driver_door_open", "Driver Door", BinarySensorDeviceClass.DOOR),
    ("passenger_door_open", "Passenger Door", BinarySensorDeviceClass.DOOR),
    ("rear_left_door_open", "Rear Left Door", BinarySensorDeviceClass.DOOR),
    ("rear_right_door_open", "Rear Right Door", BinarySensorDeviceClass.DOOR),
    ("boot_open", "Boot", BinarySensorDeviceClass.DOOR),
    ("bonnet_open", "Bonnet", BinarySensorDeviceClass.DOOR),
    ("driver_window_open", "Driver Window", BinarySensorDeviceClass.WINDOW),
    ("passenger_window_open", "Passenger Window", BinarySensorDeviceClass.WINDOW),
    ("rear_left_window_open", "Rear Left Window", BinarySensorDeviceClass.WINDOW),
    ("rear_right_window_open", "Rear Right Window", BinarySensorDeviceClass.WINDOW),
    ("sunroof_open", "Sunroof", BinarySensorDeviceClass.OPENING),
    ("climate_running", "Climate Running", BinarySensorDeviceClass.RUNNING),
    ("can_bus_active", "CAN Bus Active", BinarySensorDeviceClass.RUNNING),
    ("handbrake", "Handbrake", None),
]


async def async_setup_entry(hass, entry, async_add_entities):
    c = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    async_add_entities([MgIndiaBinary(c, *b) for b in BINS])


class MgIndiaBinary(MgIndiaEntity, BinarySensorEntity):
    def __init__(self, c, key, name, cls):
        super().__init__(c, key, name)
        self._attr_device_class = cls

    @property
    def is_on(self):
        return getattr(self.status, self._key, None) if self.status else None
