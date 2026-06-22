from __future__ import annotations
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from .api import MgIndiaClient
from .const import CONF_PASSWORD, CONF_PHONE, CONF_PIN_HASH, CONF_VIN, DOMAIN
from .coordinator import MgIndiaCoordinator
PLATFORMS = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.LOCK,
    Platform.CLIMATE,
    Platform.COVER,
    Platform.BUTTON,
    Platform.SELECT]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    data = {**entry.data, **entry.options}
    client = MgIndiaClient(
        async_get_clientsession(hass),
        data[CONF_PHONE],
        data[CONF_PASSWORD],
        data.get(CONF_VIN),
        data.get(CONF_PIN_HASH))
    coordinator = MgIndiaCoordinator(hass, client)
    await coordinator.async_config_entry_first_refresh()
    entry.async_on_unload(entry.add_update_listener(async_update_options))
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "client": client, "coordinator": coordinator}
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return ok


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
