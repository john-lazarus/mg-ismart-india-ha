from __future__ import annotations
import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_call_later
from mg_ismart_india_client import MgIndiaClient, MgIndiaLoginRejected
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


def _cancel_retry(hass: HomeAssistant, entry_id: str) -> None:
    if cancel := hass.data.get(DOMAIN, {}).get("retries", {}).pop(entry_id, None):
        cancel()


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    _cancel_retry(hass, entry.entry_id)
    data = {**entry.data, **entry.options}
    # MG India allows one session per account, so entries sharing a phone
    # share one client; for_vehicle() makes them take turns on it.
    phone = normalize_phone(data[CONF_PHONE])
    accounts = hass.data.setdefault(DOMAIN, {}).setdefault("accounts", {})
    account = accounts.get(phone)
    if account is None:
        account = accounts[phone] = {
            "client": MgIndiaClient(
                async_get_clientsession(hass), phone, data[CONF_PASSWORD]
            ),
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
        data.get(CONF_VIN),
        data.get(CONF_PIN_HASH),
        data.get(CONF_SCAN_INTERVAL_PARKED, DEFAULT_SCAN_INTERVAL_PARKED),
        data.get(CONF_SCAN_INTERVAL_ACTIVE, DEFAULT_SCAN_INTERVAL_ACTIVE),
    )
    account["entries"].add(entry.entry_id)
    try:
        await coordinator.async_config_entry_first_refresh()
    except BaseException as err:
        account["entries"].discard(entry.entry_id)
        if not account["entries"]:
            accounts.pop(phone, None)
        if not isinstance(err, ConfigEntryNotReady) or isinstance(
            err.__cause__, MgIndiaLoginRejected
        ):
            raise
        # HA's fast setup retry would wake a sleeping car every minute or so;
        # retry once at the parked interval instead.
        minutes = coordinator.parked_min
        _LOGGER.warning(
            "%s did not answer (%s); retrying in %d minutes",
            entry.title, err.__cause__, minutes,
        )
        entry_id = entry.entry_id

        @callback
        def _retry(_now) -> None:
            hass.data[DOMAIN].get("retries", {}).pop(entry_id, None)
            e = hass.config_entries.async_get_entry(entry_id)
            if e is not None and not e.disabled_by:
                hass.config_entries.async_schedule_reload(entry_id)

        hass.data[DOMAIN].setdefault("retries", {})[entry_id] = async_call_later(
            hass, minutes * 60, _retry
        )
        raise ConfigEntryError(
            f"Car did not answer; retrying in {minutes} minutes"
        ) from err
    entry.async_on_unload(entry.add_update_listener(async_update_options))
    hass.data[DOMAIN][entry.entry_id] = {
        "client": account["client"],
        "coordinator": coordinator,
        "account": phone,
    }
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    _cancel_retry(hass, entry.entry_id)
    ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if ok:
        phone = hass.data[DOMAIN].pop(entry.entry_id)["account"]
        accounts = hass.data[DOMAIN]["accounts"]
        accounts[phone]["entries"].discard(entry.entry_id)
        if not accounts[phone]["entries"]:
            del accounts[phone]
    return ok


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    _cancel_retry(hass, entry.entry_id)


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
