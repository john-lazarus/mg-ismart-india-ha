from __future__ import annotations

import asyncio
import types

from mg_ismart_india_client import (
    Capabilities,
    Snapshot,
    Status,
    Vehicle,
)
from custom_components.mg_ismart_india.const import (
    CONF_PASSWORD,
    CONF_PHONE,
    CONF_PIN_HASH,
    CONF_VIN,
)
from custom_components.mg_ismart_india.diagnostics import (
    async_get_config_entry_diagnostics,
)




def test_diagnostics_redacts_credentials_and_uses_slots_dataclass():
    async def run():
        entry = types.SimpleNamespace(
            data={
                CONF_PHONE: "9876543210",
                CONF_PASSWORD: "secret",
                CONF_PIN_HASH: "hash",
                CONF_VIN: "VIN12345678901234",
            },
            entry_id="entry1",
        )
        snap = Snapshot(
            Vehicle("VIN12345678901234", "Car"), Capabilities(climate=True), Status()
        )
        coordinator = types.SimpleNamespace(data=snap)
        hass = types.SimpleNamespace(
            data={"mg_ismart_india": {"entry1": {"coordinator": coordinator}}}
        )

        diag = await async_get_config_entry_diagnostics(hass, entry)

        text = repr(diag)
        assert "secret" not in text
        assert "9876543210" not in text
        assert "VIN12345678901234" not in text
        assert diag["snapshot"]["capabilities"]["climate"] is True
        assert diag["control_pin_configured"] is True

    asyncio.run(run())


def test_optional_controls_hidden_when_capabilities_absent():
    async def run():
        from custom_components.mg_ismart_india.cover import (
            async_setup_entry as setup_covers,
        )
        from custom_components.mg_ismart_india.select import (
            async_setup_entry as setup_selects,
        )
        from custom_components.mg_ismart_india.button import (
            async_setup_entry as setup_buttons,
        )

        snap = Snapshot(Vehicle("VIN12345678901234", "Car"), Capabilities(), Status())
        coordinator = types.SimpleNamespace(data=snap)
        hass = types.SimpleNamespace(
            data={
                "mg_ismart_india": {
                    "entry1": {"coordinator": coordinator, "client": object()}
                }
            }
        )
        entry = types.SimpleNamespace(entry_id="entry1")
        added = []

        def add_entities(entities):
            added.extend(entities)

        await setup_covers(hass, entry, add_entities)
        await setup_selects(hass, entry, add_entities)
        await setup_buttons(hass, entry, add_entities)

        names = {entity._attr_name for entity in added}
        assert "Windows" not in names
        assert "Sunroof" not in names
        assert "Driver Heated Seat" not in names
        assert "Passenger Heated Seat" not in names
        assert "Release Tailgate" not in names
        assert "Find My Car" in names

    asyncio.run(run())


def test_control_entities_unavailable_while_remote_command_running():
    from custom_components.mg_ismart_india.climate import MgClimate
    from custom_components.mg_ismart_india.lock import MgDoorLock

    snap = Snapshot(
        Vehicle("VIN12345678901234", "Car"),
        Capabilities(climate=True, door_lock=True),
        Status(locked=True),
    )
    coordinator = types.SimpleNamespace(
        data=snap,
        last_update_success=True,
        command_in_progress=True,
    )
    client = types.SimpleNamespace(has_pin=True)

    assert MgDoorLock(coordinator, client).available is False
    assert MgClimate(coordinator, client).available is False
