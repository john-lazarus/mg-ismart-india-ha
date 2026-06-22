from __future__ import annotations

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import UnitOfTemperature

from .const import DOMAIN
from .entity import MgIndiaEntity


async def async_setup_entry(hass, entry, async_add_entities):
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    async_add_entities([MgClimate(coordinator, data["client"])])


class MgClimate(MgIndiaEntity, ClimateEntity):
    _attr_supported_features = (
        ClimateEntityFeature.TURN_ON | ClimateEntityFeature.TURN_OFF
    )
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.COOL]
    _attr_temperature_unit = UnitOfTemperature.CELSIUS

    def __init__(self, coordinator, client):
        super().__init__(coordinator, "climate", "Climate")
        self.client = client

    @property
    def available(self):
        return super().available and self.client.has_pin

    @property
    def hvac_mode(self):
        return (
            HVACMode.COOL
            if self.status and self.status.climate_running
            else HVACMode.OFF
        )

    async def async_set_hvac_mode(self, hvac_mode):
        await self.client.control_climate(hvac_mode == HVACMode.COOL)
        await self.coordinator.async_request_refresh()

    async def async_turn_on(self):
        await self.async_set_hvac_mode(HVACMode.COOL)

    async def async_turn_off(self):
        await self.async_set_hvac_mode(HVACMode.OFF)
