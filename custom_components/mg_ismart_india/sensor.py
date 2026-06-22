from __future__ import annotations
from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    UnitOfLength,
    UnitOfElectricPotential,
    UnitOfTemperature,
)
from .const import DOMAIN
from .entity import MgIndiaEntity

SENSORS = [
    ("fuel_level", "Fuel Level", PERCENTAGE, SensorDeviceClass.BATTERY, None),
    ("range_km", "Range", UnitOfLength.KILOMETERS, None, None),
    (
        "odometer_km",
        "Odometer",
        UnitOfLength.KILOMETERS,
        SensorDeviceClass.DISTANCE,
        SensorStateClass.TOTAL_INCREASING,
    ),
    (
        "interior_temperature",
        "Interior Temperature",
        UnitOfTemperature.CELSIUS,
        SensorDeviceClass.TEMPERATURE,
        None,
    ),
    (
        "exterior_temperature",
        "Exterior Temperature",
        UnitOfTemperature.CELSIUS,
        SensorDeviceClass.TEMPERATURE,
        None,
    ),
    (
        "aux_battery_voltage",
        "Aux Battery Voltage",
        UnitOfElectricPotential.VOLT,
        SensorDeviceClass.VOLTAGE,
        None,
    ),
    ("status_time", "Vehicle Status Time", None, SensorDeviceClass.TIMESTAMP, None),
    (
        "last_can_activity",
        "Last Vehicle Activity",
        None,
        SensorDeviceClass.TIMESTAMP,
        None,
    ),
]


async def async_setup_entry(hass, entry, async_add_entities):
    c = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    async_add_entities([MgIndiaSensor(c, *s) for s in SENSORS])


class MgIndiaSensor(MgIndiaEntity, SensorEntity):
    def __init__(self, c, key, name, unit, device_class, state_class):
        super().__init__(c, key, name)
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = device_class
        self._attr_state_class = state_class

    @property
    def native_value(self):
        import datetime

        v = getattr(self.status, self._key, None) if self.status else None
        if self._attr_device_class == SensorDeviceClass.TIMESTAMP and isinstance(
            v, int
        ):
            return datetime.datetime.fromtimestamp(v, datetime.UTC)
        return v
