"""Tests for config_flow"""

from typing import Any
from uuid import uuid4

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_BRIGHTNESS, CONF_ENTITIES, CONF_FRIENDLY_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.entity_registry import async_get as async_get_entity_registry
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.lightener import const


async def test_config_flow_steps(hass: HomeAssistant) -> None:
    """Test if the full config flow works"""

    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["last_step"] is False

    assert get_required(result, "name") is True

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"name": "Test Name"}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "lights"
    assert result["last_step"] is False

    assert get_required(result, "controlled_entities") is True

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"controlled_entities": ["light.test1"]},
    )

    assert result["type"] == "form"
    assert result["step_id"] == "light_configuration"
    assert result["last_step"] is True
    assert result["description_placeholders"] == {"light_name": "test1"}

    assert get_required(result, "brightness") is False

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


async def test_options_flow_steps(hass: HomeAssistant) -> None:
    """Test if the full options flow works"""

    entry = MockConfigEntry(
        domain="lightener",
        unique_id=str(uuid4()),
        data={
            CONF_ENTITIES: {
                "light.test1": {CONF_BRIGHTNESS: {"10": "20"}},
                "light.test2": {CONF_BRIGHTNESS: {"30": "40"}},
            }
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] == "form"
    assert result["step_id"] == "init"
    assert result["last_step"] is False

    assert get_default(result, "controlled_entities") == ["light.test1", "light.test2"]

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"controlled_entities": ["light.test1"]},
    )

    assert result["type"] == "form"
    assert result["step_id"] == "light_configuration"
    assert result["last_step"] is True

    assert get_suggested(result, "brightness") == "10: 20"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"brightness": "50:60"},
    )

    assert result["type"] == "create_entry"
    assert result["title"] == ""
    assert result["data"] == {}

    assert entry.data == {
        CONF_ENTITIES: {"light.test1": {CONF_BRIGHTNESS: {"50": "60"}}}
    }

    assert entry.options == {}


async def test_step_lights_no_lightener(hass: HomeAssistant) -> None:
    """Test if the list of lights to select doesn't include the lightener being configured"""

    entry = MockConfigEntry(
        domain="lightener",
        unique_id=str(uuid4()),
        data={CONF_ENTITIES: {"light.test1": {CONF_BRIGHTNESS: {"10": "20"}}}},
    )
    entry.add_to_hass(hass)

    entity_registry = async_get_entity_registry(hass)

    entity_registry.async_get_or_create(
        domain="light",
        platform="lightener",
        unique_id=str(uuid4()),
        config_entry=entry,
        suggested_object_id="test_lightener",
    )

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert get_default(result, "controlled_entities") == ["light.test1"]


async def test_step_light_configuration_multiple_lights(hass: HomeAssistant) -> None:
    """Test if the flow works when multiple lights are selected"""

    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"name": "Test Name"}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"controlled_entities": ["light.test1", "light.test2"]},
    )

    assert result["step_id"] == "light_configuration"
    assert result["last_step"] is False

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"brightness": "50:60"},
    )

    assert result["step_id"] == "light_configuration"
    assert result["last_step"] is True


async def test_step_light_configuration_brightness_validation(
    hass: HomeAssistant,
) -> None:
    """Test the input validation of the brightness field"""

    async def assert_value(must_pass, value, error_value=None):
        result = await hass.config_entries.flow.async_init(
            const.DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"name": "Test Name"}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"controlled_entities": ["light.test1"]},
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"brightness": value},
        )

        if must_pass is True:
            assert (
                result["type"] == "create_entry"
            ), f"{value} => '{result['description_placeholders']['error_entry']}'"
        else:
            assert result["errors"]["brightness"] == "invalid_brightness", value
            assert (
                result["description_placeholders"]["error_entry"] == value
                or error_value
            ), value

    # Wrong format
    await assert_value(False, "50:60x")
    await assert_value(False, "x50:60")
    await assert_value(False, "x50:60")
    await assert_value(False, "50-60")
    await assert_value(False, "50=60x")
    await assert_value(False, "50 60x")
    await assert_value(False, "-50:-60")
    await assert_value(False, "bla")
    await assert_value(False, "10: 20\n50:60x", "50:60x")

    # Wrong values
    await assert_value(False, "0:50")
    await assert_value(False, "101:50")
    await assert_value(False, "50:101")

    # Good ones
    await assert_value(True, "1:0")  # Lowest values
    await assert_value(True, "100:100")  # Highest values
    await assert_value(True, "50:60")
    await assert_value(True, " 50:60")
    await assert_value(True, "   50    :     60     ")
    await assert_value(True, "50:60 ")
    await assert_value(True, "50 : 60")
    await assert_value(True, "50: 60")
    await assert_value(True, "50 :60")
    await assert_value(True, "50 :60\n   10: 20    \n30:40")
    await assert_value(True, "")


def get_default(form: FlowResult, key: str) -> Any:
    """Get default value for key in voluptuous schema."""

    for schema_key in form["data_schema"].schema:
        if schema_key == key:
            if schema_key.default != vol.UNDEFINED:
                return schema_key.default()
            return None

    raise KeyError(f"Key '{key}' not found")


def get_suggested(form: FlowResult, key: str) -> Any:
    """Get default value for key in voluptuous schema."""

    for schema_key in form["data_schema"].schema:
        if schema_key == key:
            if (
                schema_key.description is None
                or "suggested_value" not in schema_key.description
            ):
                return None
            return schema_key.description["suggested_value"]

    raise KeyError(f"Key '{key}' not found")


def get_required(form: FlowResult, key: str) -> Any:
    """Get default value for key in voluptuous schema."""

    for schema_key in form["data_schema"].schema:
        if schema_key == key:
            return isinstance(schema_key, vol.Required)

    raise KeyError(f"Key '{key}' not found")
