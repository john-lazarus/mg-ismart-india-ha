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

    asyncio.run(run())
