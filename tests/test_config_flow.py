"""Tests for config_flow"""

# pylint: disable=missing-function-docstring

from homeassistant import config_entries
from homeassistant.const import CONF_BRIGHTNESS, CONF_ENTITIES, CONF_FRIENDLY_NAME
from homeassistant.core import HomeAssistant

from custom_components.lightener import const


async def test_config_flow_steps(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    # assert result["last_step"] is False

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"name": "Test Name"}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "lights"
    assert result["last_step"] is False

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"controlled_entities": ["light.test1"]},
    )

    assert result["type"] == "form"
    assert result["step_id"] == "light_configuration"
    assert result["last_step"] is True

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"brightness": "10:20"},
    )

    assert result["type"] == "create_entry"
    assert result["title"] == "Test Name"
    assert result["data"] == {
        CONF_FRIENDLY_NAME: "Test Name",
        CONF_ENTITIES: {"light.test1": {CONF_BRIGHTNESS: {"10": "20"}}},
    }


async def test_config_flow_name_required(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"name": ""}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "lights"
    assert result["last_step"] is False
