from __future__ import annotations
from dataclasses import asdict, is_dataclass

from .const import CONF_PASSWORD, CONF_PHONE, CONF_PIN_HASH, CONF_VIN, DOMAIN


def _safe_dataclass(value):
    return asdict(value) if is_dataclass(value) else None


async def async_get_config_entry_diagnostics(hass, entry):
    data = dict(entry.data)
    for key in (CONF_PASSWORD, CONF_PIN_HASH, CONF_PHONE, CONF_VIN):
        data.pop(key, None)
    runtime = hass.data.get(DOMAIN, {}).get(entry.entry_id, {})
    snap = getattr(runtime.get("coordinator"), "data", None)
    vehicle = getattr(snap, "vehicle", None) if snap else None
    return {
        "entry": data,
        "control_pin_configured": bool(
            entry.data.get(CONF_PIN_HASH) or entry.options.get(CONF_PIN_HASH)
        ),
        "snapshot": {
            "vehicle": {
                "name": getattr(vehicle, "name", None),
                "model": getattr(vehicle, "model", None),
                "model_year": getattr(vehicle, "model_year", None),
            }
            if vehicle
            else None,
            "capabilities": _safe_dataclass(getattr(snap, "capabilities", None))
            if snap
            else None,
        },
    }
