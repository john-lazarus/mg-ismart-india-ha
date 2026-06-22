
from custom_components.mg_ismart_india.config_flow import options_from_user_input
from custom_components.mg_ismart_india.const import CONF_PIN_HASH


def test_options_hashes_new_pin():
    data = options_from_user_input({"pin": "4321"})
    assert CONF_PIN_HASH in data
    assert data[CONF_PIN_HASH]
    assert data[CONF_PIN_HASH] != "4321"
    assert len(data[CONF_PIN_HASH]) == 32


def test_options_can_clear_pin():
    assert options_from_user_input({"clear_pin": True}) == {CONF_PIN_HASH: ""}


def test_empty_options_keeps_existing_pin():
    assert options_from_user_input({}) == {}



def test_options_flow_constructor_does_not_assign_config_entry():
    from custom_components.mg_ismart_india.config_flow import MgIndiaConfigFlow, MgIndiaOptionsFlow
    flow = MgIndiaConfigFlow.async_get_options_flow(object())
    assert isinstance(flow, MgIndiaOptionsFlow)



def test_options_flow_constructor_matches_new_ha_api():
    import inspect
    from custom_components.mg_ismart_india.config_flow import MgIndiaOptionsFlow
    assert list(inspect.signature(MgIndiaOptionsFlow).parameters) == []
