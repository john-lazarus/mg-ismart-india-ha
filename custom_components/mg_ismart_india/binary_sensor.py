from __future__ import annotations
from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorDeviceClass,
)
from .const import DOMAIN
from .coordinator import is_electric
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


CHARGE_BINS = [
    ("charging", "Charging", BinarySensorDeviceClass.BATTERY_CHARGING, "is_charging"),
    ("plugged_in", "Plugged In", BinarySensorDeviceClass.PLUG, "is_plugged_in"),
]


async def async_setup_entry(hass, entry, async_add_entities):
    c = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    ev = is_electric(c.data.vehicle)
    async_add_entities(
        [MgIndiaBinary(c, *b) for b in BINS]
        + [MgChargeBinary(c, *b) for b in CHARGE_BINS if ev]
        + [MgCommandInProgress(c)]
    )


class MgIndiaBinary(MgIndiaEntity, BinarySensorEntity):
    def __init__(self, c, key, name, cls):
        super().__init__(c, key, name)
        self._attr_device_class = cls

    @property
    def is_on(self):
        return getattr(self.status, self._key, None) if self.status else None


class MgChargeBinary(MgIndiaEntity, BinarySensorEntity):
    def __init__(self, c, key, name, cls, attr):
        super().__init__(c, key, name)
        self._attr_device_class = cls
        self._attr = attr

    @property
    def is_on(self):
        return getattr(getattr(self.status, "charge", None), self._attr, None)


class MgCommandInProgress(MgIndiaEntity, BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.RUNNING

    def __init__(self, c):
        super().__init__(c, "remote_command_in_progress", "Remote Command In Progress")

    @property
    def is_on(self):
        return getattr(self.coordinator, "command_in_progress", False)

    @property
    def extra_state_attributes(self):
        return {
            "command": getattr(self.coordinator, "command_name", None),
            "status": getattr(self.coordinator, "last_command_status", None),
            "error": getattr(self.coordinator, "last_command_error", None),
        }
