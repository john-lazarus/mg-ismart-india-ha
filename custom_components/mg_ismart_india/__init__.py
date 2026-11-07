from __future__ import annotations
import asyncio
import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from mg_ismart_india_client import MgIndiaClient
from mg_ismart_india_client.crypto import normalize_phone
from .const import (
    CONF_PASSWORD,
    CONF_PHONE,
    CONF_PIN_HASH,
    CONF_SCAN_INTERVAL_ACTIVE,
    CONF_SCAN_INTERVAL_PARKED,
    CONF_VIN,
    DEFAULT_SCAN_INTERVAL_ACTIVE,
    DEFAULT_SCAN_INTERVAL_PARKED,
    DOMAIN,
)
from .coordinator import MgIndiaCoordinator

_LOGGER = logging.getLogger(__name__)
PLATFORMS = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.DEVICE_TRACKER,
    Platform.LOCK,
    Platform.CLIMATE,
    Platform.COVER,
    Platform.BUTTON,
    Platform.SELECT,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    data = {**entry.data, **entry.options}
    # MG India allows one session per account, so entries sharing a phone
    # share one client and take turns on it.
    phone = normalize_phone(data[CONF_PHONE])
    accounts = hass.data.setdefault(DOMAIN, {}).setdefault("accounts", {})
    account = accounts.get(phone)
    if account is None:
        account = accounts[phone] = {
            "client": MgIndiaClient(
                async_get_clientsession(hass), phone, data[CONF_PASSWORD]
            ),
            "lock": asyncio.Lock(),
            "entries": set(),
        }
    elif account["client"].password != data[CONF_PASSWORD]:
        _LOGGER.warning(
            "Entries for the same MG account have different passwords; using the newest"
        )
        account["client"].password = data[CONF_PASSWORD]
    coordinator = MgIndiaCoordinator(
        hass,
        account["client"],
        account["lock"],
        data.get(CONF_VIN),
        data.get(CONF_PIN_HASH),
        data.get(CONF_SCAN_INTERVAL_PARKED, DEFAULT_SCAN_INTERVAL_PARKED),
        data.get(CONF_SCAN_INTERVAL_ACTIVE, DEFAULT_SCAN_INTERVAL_ACTIVE),
    )
    await coordinator.async_config_entry_first_refresh()
    account["entries"].add(entry.entry_id)
    entry.async_on_unload(entry.add_update_listener(async_update_options))
    hass.data[DOMAIN][entry.entry_id] = {
        "client": account["client"],
        "coordinator": coordinator,
        "account": phone,
    }
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if ok:
        phone = hass.data[DOMAIN].pop(entry.entry_id)["account"]
        accounts = hass.data[DOMAIN]["accounts"]
        accounts[phone]["entries"].discard(entry.entry_id)
        if not accounts[phone]["entries"]:
            del accounts[phone]
    return ok


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
