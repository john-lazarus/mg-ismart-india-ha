from __future__ import annotations
from .const import DOMAIN, CONF_PASSWORD, CONF_PIN_HASH


async def async_get_config_entry_diagnostics(hass, entry):
    data = dict(entry.data)
    data.pop(CONF_PASSWORD, None)
    data.pop(CONF_PIN_HASH, None)
    runtime = hass.data.get(DOMAIN, {}).get(entry.entry_id, {})
    snap = getattr(runtime.get('coordinator'), 'data', None)
    return {
        'entry': data,
        'snapshot': {
            'vehicle': getattr(
                getattr(
                    snap,
                    'vehicle',
                    None),
                'vin',
                None),
            'capabilities': getattr(
                snap,
                'capabilities',
                None).__dict__ if snap else None}}
