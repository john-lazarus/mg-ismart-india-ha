import asyncio
import types
from datetime import timedelta

from custom_components.mg_ismart_india import async_setup_entry, async_unload_entry
from custom_components.mg_ismart_india.config_flow import options_from_user_input
from custom_components.mg_ismart_india.coordinator import MgIndiaCoordinator
from mg_ismart_india_client import Capabilities, Snapshot, Status, Vehicle


def test_interval_parked_vs_active():
    async def run():
        status = Status()
        coord = MgIndiaCoordinator(None, None, asyncio.Lock(), "V", None, 30, 5)

        async def fake(c):
            return Snapshot(Vehicle("V", "Car"), Capabilities(), status)

        coord._fetch = fake
        coord.client = types.SimpleNamespace()
        await coord._async_update_data()
        assert coord.update_interval == timedelta(minutes=30)
        assert coord.last_update.tzinfo is not None
        status.climate_running = True
        await coord._async_update_data()
        assert coord.update_interval == timedelta(minutes=5)

    asyncio.run(run())


def test_two_entries_share_one_account_client(monkeypatch):
    async def run():
        import custom_components.mg_ismart_india as mod

        seen = []

        async def fake_fetch(self, c):
            seen.append((c.vin, c.pin_hash))
            return Snapshot(Vehicle(c.vin, "Car"), Capabilities(), Status())

        monkeypatch.setattr(MgIndiaCoordinator, "_fetch", fake_fetch)
        monkeypatch.setattr(mod, "async_get_clientsession", lambda hass: None)

        async def ok(*a, **k):
            return True

        hass = types.SimpleNamespace(
            data={},
            config_entries=types.SimpleNamespace(
                async_forward_entry_setups=ok, async_unload_platforms=ok
            ),
        )

        def entry(eid, vin, pin):
            return types.SimpleNamespace(
                entry_id=eid,
                data={"phone": "+91 98765 43210", "password": "pw", "vin": vin, "pin_hash": pin},
                options={},
                async_on_unload=lambda cb: None,
                add_update_listener=lambda cb: None,
            )

        a, b = entry("a", "VIN_A", "pa"), entry("b", "VIN_B", None)
        # Skip HA's first-refresh plumbing: run the real update path directly.
        async def first(self):
            await self._async_update_data()

        monkeypatch.setattr(MgIndiaCoordinator, "async_config_entry_first_refresh", first)
        await async_setup_entry(hass, a)
        await async_setup_entry(hass, b)
        accounts = hass.data["mg_ismart_india"]["accounts"]
        assert len(accounts) == 1
        ca = hass.data["mg_ismart_india"]["a"]["coordinator"]
        cb = hass.data["mg_ismart_india"]["b"]["coordinator"]
        assert ca.client is cb.client and ca.account_lock is cb.account_lock
        assert seen == [("VIN_A", "pa"), ("VIN_B", None)]
        assert ca.has_pin and not cb.has_pin
        await async_unload_entry(hass, a)
        assert len(accounts) == 1
        await async_unload_entry(hass, b)
        assert accounts == {}

    asyncio.run(run())


def test_options_pass_intervals_and_keep_pin_behaviour():
    iv = {"scan_interval_parked": 60, "scan_interval_active": 2}
    assert options_from_user_input(iv) == iv
    assert options_from_user_input({**iv, "clear_pin": True, "pin": "1234"}) == {
        **iv,
        "pin_hash": "",
    }
    assert len(options_from_user_input({"pin": "1234"})["pin_hash"]) == 32


def test_failed_first_refresh_leaves_no_account_record(monkeypatch):
    import pytest

    import custom_components.mg_ismart_india as mod

    async def boom(self):
        raise RuntimeError("login failed")

    monkeypatch.setattr(MgIndiaCoordinator, "async_config_entry_first_refresh", boom)
    monkeypatch.setattr(mod, "async_get_clientsession", lambda hass: None)
    hass = types.SimpleNamespace(data={})
    e = types.SimpleNamespace(
        entry_id="a",
        data={"phone": "+91 98765 43210", "password": "pw", "vin": "V", "pin_hash": None},
        options={},
    )
    with pytest.raises(RuntimeError):
        asyncio.run(async_setup_entry(hass, e))
    assert hass.data["mg_ismart_india"]["accounts"] == {}
