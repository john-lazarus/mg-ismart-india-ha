from __future__ import annotations

import asyncio
import types

from custom_components.mg_ismart_india.api.client import MgIndiaClient
from custom_components.mg_ismart_india.api.models import (
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


class _Response:
    status = 200
    headers = {}

    async def text(self):
        return "ok"

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False


class _Session:
    def __init__(self, client=None):
        self.client = client
        self.posts = 0

    def post(self, *args, **kwargs):
        self.posts += 1
        if self.client is not None:
            assert self.client.token == "token"
            assert self.client.uid == "uid"
            assert self.client.vin == "VIN12345678901234"
        return _Response()


def test_verify_pin_logs_in_before_pin_request(monkeypatch):
    async def run():
        client = MgIndiaClient(
            _Session(),
            "9876543210",
            "secret",
            vin="VIN12345678901234",
            pin_hash="A" * 32,
        )
        client.session.client = client
        calls = []

        async def login():
            calls.append("login")
            client.uid = "uid"
            client.token = "token"

        monkeypatch.setattr(client, "login", login)
        monkeypatch.setattr(
            "custom_components.mg_ismart_india.api.client.decode_pin_response",
            lambda _text: {"result": 0},
        )

        await client.verify_pin()

        assert calls == ["login"]
        assert client.session.posts == 1

    asyncio.run(run())


def test_control_polls_with_returned_event_id(monkeypatch):
    async def run():
        client = MgIndiaClient(
            _Session(),
            "9876543210",
            "secret",
            vin="VIN12345678901234",
            pin_hash="A" * 32,
        )
        client.uid = "uid"
        client.token = "token"
        event_ids = []
        responses = [
            ({"result": 4, "eventID": 123}, None),
            ({"result": 0}, {"rvcReqSts": b"\x02"}),
        ]

        async def verify_pin():
            return None

        def encode(_uid, _token, _vin, event_id, _typ, _params):
            event_ids.append(event_id)
            return "body"

        def decode(_text):
            return responses.pop(0)

        monkeypatch.setattr(client, "verify_pin", verify_pin)
        monkeypatch.setattr(
            "custom_components.mg_ismart_india.api.client.encode_control_request",
            encode,
        )
        monkeypatch.setattr(
            "custom_components.mg_ismart_india.api.client.decode_control_response",
            decode,
        )

        await client._control("Climate", 6, [(1, b"\x01")])

        assert event_ids == [0, 123]

    asyncio.run(run())


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


def test_control_methods_use_mg_india_parameter_shapes(monkeypatch):
    async def run():
        client = MgIndiaClient(
            _Session(),
            "9876543210",
            "secret",
            vin="VIN12345678901234",
            pin_hash="A" * 32,
        )
        calls = []

        async def fake_control(name, typ, params):
            calls.append((name, typ, params))

        monkeypatch.setattr(client, "_control", fake_control)

        await client.control_door_lock(False)
        await client.control_climate(True)
        await client.find_my_car()
        await client.release_tailgate()
        await client.control_windows(True, (9, 10, 11, 12))
        await client.control_sunroof(False)
        await client.control_heated_seats(2, 1)

        assert calls[0] == (
            "Door lock",
            2,
            [(4, b"\x00"), (5, b"\x00"), (6, b"\x00"), (7, b"\x03"), (255, b"\x00")],
        )
        assert calls[1] == (
            "Climate",
            6,
            [(19, b"\x03"), (20, b"\x03"), (255, b"\x00")],
        )
        assert calls[2] == (
            "Find my car",
            0,
            [(1, b"\x01"), (2, b"\x01"), (3, b"\x01"), (255, b"\x00")],
        )
        assert calls[3] == (
            "Tailgate",
            2,
            [(4, b"\x00"), (5, b"\x00"), (6, b"\x00"), (7, b"\x02"), (255, b"\x00")],
        )
        assert calls[4] == (
            "Windows",
            3,
            [
                (8, b"\x00"),
                (9, b"\x01"),
                (10, b"\x01"),
                (11, b"\x01"),
                (12, b"\x01"),
                (13, b"\x03"),
            ],
        )
        assert calls[5] == (
            "Sunroof",
            3,
            [
                (8, b"\x01"),
                (9, b"\x00"),
                (10, b"\x00"),
                (11, b"\x00"),
                (12, b"\x00"),
                (13, b"\x00"),
            ],
        )
        assert calls[6] == (
            "Heated seats",
            5,
            [(17, b"\x02"), (18, b"\x01"), (255, b"\x00")],
        )

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


def test_control_retries_once_after_bad_control_response_frame(monkeypatch):
    async def run():
        client = MgIndiaClient(
            _Session(),
            "9876543210",
            "secret",
            vin="VIN12345678901234",
            pin_hash="A" * 32,
        )
        client.uid = "uid"
        client.token = "token"
        logins = []
        decodes = [
            ValueError("unexpected TAP v2.1 response framing"),
            ({"result": 0}, {"rvcReqSts": b"\x02"}),
        ]

        async def verify_pin():
            return None

        async def login():
            logins.append("login")
            client.uid = "uid"
            client.token = "token2"

        def decode(_text):
            item = decodes.pop(0)
            if isinstance(item, Exception):
                raise item
            return item

        monkeypatch.setattr(client, "verify_pin", verify_pin)
        monkeypatch.setattr(client, "login", login)
        monkeypatch.setattr(
            "custom_components.mg_ismart_india.api.client.encode_control_request",
            lambda *_args: "body",
        )
        monkeypatch.setattr(
            "custom_components.mg_ismart_india.api.client.decode_control_response",
            decode,
        )

        await client._control("Door lock", 1, [])

        assert logins == ["login"]

    asyncio.run(run())
