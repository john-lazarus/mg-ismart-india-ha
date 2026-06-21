from __future__ import annotations
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN


class MgIndiaEntity(CoordinatorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, key: str, name: str):
        super().__init__(coordinator)
        self._key = key
        self._attr_name = name
        vin = getattr(
            coordinator.data.vehicle,
            'vin',
            'unknown') if coordinator.data else 'unknown'
        self._attr_unique_id = f"{DOMAIN}_{vin}_{key}"

    @property
    def device_info(self):
        v = self.coordinator.data.vehicle
        return {"identifiers": {(DOMAIN,
                                 v.vin)},
                "manufacturer": "MG",
                "name": v.name,
                "model": v.model,
                "sw_version": "MG iSMART India"}

    @property
    def status(
        self): return self.coordinator.data.status if self.coordinator.data else None

    @property
    def caps(
        self): return self.coordinator.data.capabilities if self.coordinator.data else None
