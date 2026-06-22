from __future__ import annotations
from typing import Any
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from .api import MgIndiaClient, MgIndiaApiError, hash_control_pin
from .const import (
    CONF_PASSWORD,
    CONF_PHONE,
    CONF_PIN_HASH,
    CONF_VEHICLE_NAME,
    CONF_VIN,
    DOMAIN,
)


def options_from_user_input(user_input: dict[str, Any]) -> dict[str, Any]:
    if user_input.get("clear_pin"):
        return {CONF_PIN_HASH: ""}
    pin = user_input.get("pin")
    if pin:
        return {CONF_PIN_HASH: hash_control_pin(pin)}
    return {}


class MgIndiaConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    @staticmethod
    def async_get_options_flow(config_entry):
        return MgIndiaOptionsFlow()

    def __init__(self):
        self._base = {}
        self._vehicles = []

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        errors = {}
        if user_input:
            try:
                client = MgIndiaClient(
                    async_get_clientsession(self.hass),
                    user_input[CONF_PHONE],
                    user_input[CONF_PASSWORD],
                )
                vehicles = await client.vehicles()
                if not vehicles:
                    raise MgIndiaApiError("No vehicles returned")
                self._base = {
                    CONF_PHONE: user_input[CONF_PHONE],
                    CONF_PASSWORD: user_input[CONF_PASSWORD],
                }
                pin = user_input.get("pin")
                if pin:
                    self._base[CONF_PIN_HASH] = hash_control_pin(pin)
                self._vehicles = vehicles
                if len(vehicles) == 1:
                    v = vehicles[0]
                    data = {**self._base, CONF_VIN: v.vin, CONF_VEHICLE_NAME: v.name}
                    await self.async_set_unique_id(v.vin)
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(title=v.name, data=data)
                return await self.async_step_vehicle()
            except Exception:
                errors["base"] = "cannot_connect"
        schema = vol.Schema(
            {
                vol.Required(CONF_PHONE): str,
                vol.Required(CONF_PASSWORD): str,
                vol.Optional("pin"): str,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_vehicle(self, user_input=None):
        if user_input:
            v = next(x for x in self._vehicles if x.vin == user_input[CONF_VIN])
            await self.async_set_unique_id(v.vin)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=v.name,
                data={**self._base, CONF_VIN: v.vin, CONF_VEHICLE_NAME: v.name},
            )
        return self.async_show_form(
            step_id="vehicle",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_VIN): vol.In(
                        {v.vin: f"{v.name} ({v.vin[-6:]})" for v in self._vehicles}
                    )
                }
            ),
        )


class MgIndiaOptionsFlow(config_entries.OptionsFlow):
    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        errors = {}
        if user_input is not None:
            try:
                options = {**self.config_entry.options}
                options.update(options_from_user_input(user_input))
                return self.async_create_entry(title="", data=options)
            except MgIndiaApiError:
                errors["pin"] = "invalid_pin"
        has_pin = bool(
            self.config_entry.options.get(CONF_PIN_HASH)
            or self.config_entry.data.get(CONF_PIN_HASH)
        )
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional("pin"): str,
                    vol.Optional("clear_pin", default=False): bool,
                }
            ),
            errors=errors,
            description_placeholders={
                "pin_status": "configured" if has_pin else "not configured"
            },
        )
