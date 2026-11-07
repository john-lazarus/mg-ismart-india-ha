from __future__ import annotations
from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfEnergy,
    UnitOfLength,
    UnitOfPower,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTime,
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


TYRES = [
    ("front_left_tyre_pressure", "Front Left Tyre Pressure", "front_left_tyre_psi"),
    ("front_right_tyre_pressure", "Front Right Tyre Pressure", "front_right_tyre_psi"),
    ("rear_left_tyre_pressure", "Rear Left Tyre Pressure", "rear_left_tyre_psi"),
    ("rear_right_tyre_pressure", "Rear Right Tyre Pressure", "rear_right_tyre_psi"),
]

M = SensorStateClass.MEASUREMENT
# (key, name, unit, device_class, charge attribute, state class)
CHARGE_SENSORS = [
    ("fuel_level", "Battery", PERCENTAGE, SensorDeviceClass.BATTERY, "soc", None),
    (
        "charge_time_remaining",
        "Charge Time Remaining",
        UnitOfTime.MINUTES,
        SensorDeviceClass.DURATION,
        "charge_time_remaining_min",
        None,
    ),
    (
        "charging_duration",
        "Charging Duration",
        UnitOfTime.SECONDS,
        SensorDeviceClass.DURATION,
        "charge_time_elapsed_s",
        None,
    ),
    (
        "charging_power",
        "Charging Power",
        UnitOfPower.KILO_WATT,
        SensorDeviceClass.POWER,
        "charging_power_kw",
        M,
    ),
    (
        "battery_energy",
        "Battery Energy",
        UnitOfEnergy.KILO_WATT_HOUR,
        SensorDeviceClass.ENERGY_STORAGE,
        "battery_energy_kwh",
        M,
    ),
    (
        "distance_since_last_charge",
        "Distance Since Last Charge",
        UnitOfLength.KILOMETERS,
        SensorDeviceClass.DISTANCE,
        "distance_since_last_charge_km",
        None,
    ),
    (
        "energy_since_last_charge",
        "Energy Since Last Charge",
        UnitOfEnergy.KILO_WATT_HOUR,
        SensorDeviceClass.ENERGY,
        "power_usage_since_last_charge_kwh",
        None,
    ),
    (
        "charging_voltage",
        "Charging Voltage",
        UnitOfElectricPotential.VOLT,
        SensorDeviceClass.VOLTAGE,
        "charging_voltage",
        M,
    ),
    (
        "charging_current",
        "Charging Current",
        UnitOfElectricCurrent.AMPERE,
        SensorDeviceClass.CURRENT,
        "charging_current",
        M,
    ),
]


async def async_setup_entry(hass, entry, async_add_entities):
    c = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    ev = c.data.vehicle.is_electric
    has_tyres = any(getattr(c.data.status, t[2]) is not None for t in TYRES)
    async_add_entities(
        [MgIndiaSensor(c, *s) for s in SENSORS if not (ev and s[0] == "fuel_level")]
        + [MgChargeSensor(c, *s) for s in CHARGE_SENSORS if ev]
        + [MgLastCommandSensor(c), MgLastUpdateSensor(c), MgSpeedSensor(c)]
        + [MgTyreSensor(c, *t) for t in TYRES if has_tyres]
    )


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


class MgChargeSensor(MgIndiaEntity, SensorEntity):
    def __init__(self, c, key, name, unit, device_class, attr, state_class):
        super().__init__(c, key, name)
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = device_class
        self._attr = attr
        self._attr_state_class = state_class

    @property
    def native_value(self):
        if self._attr == "soc":
            return self.coordinator.data.battery_soc
        return getattr(getattr(self.status, "charge", None), self._attr, None)


class MgLastCommandSensor(MgIndiaEntity, SensorEntity):
    def __init__(self, c):
        super().__init__(c, "last_remote_command", "Last Remote Command")

    @property
    def native_value(self):
        return getattr(self.coordinator, "last_command_status", None)

    @property
    def extra_state_attributes(self):
        return {
            "command": getattr(self.coordinator, "command_name", None),
            "error": getattr(self.coordinator, "last_command_error", None),
        }


class MgTyreSensor(MgIndiaEntity, SensorEntity):
    _attr_native_unit_of_measurement = UnitOfPressure.PSI
    _attr_device_class = SensorDeviceClass.PRESSURE
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, c, key, name, attr):
        super().__init__(c, key, name)
        self._attr = attr

    @property
    def native_value(self):
        return getattr(self.status, self._attr, None)


class MgSpeedSensor(MgIndiaEntity, SensorEntity):
    _attr_native_unit_of_measurement = UnitOfSpeed.KILOMETERS_PER_HOUR
    _attr_device_class = SensorDeviceClass.SPEED
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, c):
        super().__init__(c, "speed", "Speed")

    @property
    def native_value(self):
        gps = self.status.gps if self.status else None
        return gps.speed_kmh if gps and gps.has_fix else None


class MgLastUpdateSensor(MgIndiaEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, c):
        super().__init__(c, "last_update", "Last Update")

    @property
    def native_value(self):
        return self.coordinator.last_update
