from __future__ import annotations

from homeassistant.components.select import SelectEntity

from .const import DOMAIN
from .entity import MgIndiaEntity


async def async_setup_entry(hass, entry, async_add_entities):
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    async_add_entities([
        MgSeat(coordinator, data["client"], "driver"),
        MgSeat(coordinator, data["client"], "passenger"),
    ])


class MgSeat(MgIndiaEntity, SelectEntity):
    _attr_options = ["0", "1", "2", "3"]

    def __init__(self, coordinator, client, side):
        super().__init__(coordinator, f"{side}_heated_seat", f"{side.title()} Heated Seat")
        self.client = client
        self.side = side
        self._level = "0"

    @property
    def available(self):
        return super().available and self.client.has_pin

    @property
    def current_option(self):
        return self._level

    async def async_select_option(self, option):
        self._level = option
        driver = int(option) if self.side == "driver" else 0
        passenger = int(option) if self.side == "passenger" else 0
        await self.client.control_heated_seats(driver, passenger)
        await self.coordinator.async_request_refresh()
