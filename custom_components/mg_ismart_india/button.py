from __future__ import annotations

from homeassistant.components.button import ButtonEntity

from .const import DOMAIN
from .entity import MgIndiaEntity


async def async_setup_entry(hass, entry, async_add_entities):
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    entities = [
        MgRefreshButton(coordinator),
        MgButton(
            coordinator, data["client"], "find_my_car", "Find My Car", "find_my_car"
        ),
        MgButton(
            coordinator,
            data["client"],
            "release_tailgate",
            "Release Tailgate",
            "release_tailgate",
        ),
    ]
    async_add_entities(entities)


class MgButton(MgIndiaEntity, ButtonEntity):
    def __init__(self, coordinator, client, key, name, method):
        super().__init__(coordinator, key, name)
        self.client = client
        self.method = method

    @property
    def available(self):
        return super().available and self.client.has_pin

    async def async_press(self):
        await getattr(self.client, self.method)()
        await self.coordinator.async_request_refresh()


class MgRefreshButton(MgIndiaEntity, ButtonEntity):
    def __init__(self, coordinator):
        super().__init__(coordinator, "refresh_status", "Refresh Status")

    async def async_press(self):
        await self.coordinator.async_request_refresh()
