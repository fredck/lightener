"""Tests for the light platform"""

from uuid import uuid4

import pytest
from homeassistant.components.light import ATTR_BRIGHTNESS, ColorMode
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant

from custom_components.lightener.light import (
    LightenerLight,
    LightenerLightEntity,
    _convert_percent_to_brightness,
)

###########################################################
### LightenerLight class only tests


async def test_lightener_light_properties(hass):
    """Test all the basic properties of the LightenerLight class"""

    config = {"friendly_name": "Living Room"}
    unique_id = str(uuid4())

    lightener = LightenerLight(hass, config, unique_id)

    assert lightener.unique_id == unique_id
    assert lightener.entity_id == "light.living_room"
    assert lightener.is_on is False
    assert lightener.brightness == 255

    # Name must be empty so it'll be taken from the device
    assert lightener.name is None
    assert lightener.device_info["name"] == "Living Room"

    assert lightener.should_poll is False
    assert lightener.has_entity_name is True

    assert lightener.color_mode == ColorMode.BRIGHTNESS
    assert lightener.supported_color_modes == {ColorMode.BRIGHTNESS}
    assert lightener.icon == "mdi:lightbulb-group"


async def test_lightener_light_properties_no_unique_id(hass):
    """Test all the basic properties of the LightenerLight class when no unique id is provided"""

    config = {"friendly_name": "Living Room"}

    lightener = LightenerLight(hass, config)

    assert lightener.unique_id is None

    # Name must exist since no device will be available for this entity
    assert lightener.name == "Living Room"
    assert lightener.device_info is None


async def test_lightener_light_turn_on(hass: HomeAssistant):
    """Test the state changes of the LightenerLight class when turned on"""

    config = {"friendly_name": "Living Room"}

    lightener = LightenerLight(hass, config)

    await lightener.async_turn_on()

    assert lightener.state == STATE_ON

    await hass.async_block_till_done()

    state = hass.states.get(lightener.entity_id)
    assert state.state == STATE_ON
    assert state.attributes[ATTR_BRIGHTNESS] == 255


async def test_lightener_light_turn_on_brightness(hass: HomeAssistant):
    """Test the brightness changes of the LightenerLight class when turned on"""

    config = {"friendly_name": "Living Room"}

    lightener = LightenerLight(hass, config)

    await lightener.async_turn_on(brightness=150)
    assert lightener.brightness == 150

    await hass.async_block_till_done()

    state = hass.states.get(lightener.entity_id)
    assert state.attributes[ATTR_BRIGHTNESS] == 150


async def test_lightener_light_turn_off(hass: HomeAssistant):
    """Test the state changes of the LightenerLight class when turned off"""

    config = {"friendly_name": "Living Room"}

    lightener = LightenerLight(hass, config)

    await lightener.async_turn_on()
    await hass.async_block_till_done()
    await lightener.async_turn_off()

    assert lightener.state == STATE_OFF

    await hass.async_block_till_done()

    state = hass.states.get(lightener.entity_id)
    assert state.state == STATE_OFF


async def test_lightener_light_on_state_change(hass: HomeAssistant):
    """Test the state changes of the LightenerLight class when turned off"""

    config = {"friendly_name": "Living Room"}

    lightener = LightenerLight(hass, config)
    await lightener.async_added_to_hass()

    await lightener.async_turn_off()
    await hass.async_block_till_done()

    hass.states.async_set(lightener.entity_id, STATE_ON, {"brightness": 120})
    await hass.async_block_till_done()

    assert lightener.state == STATE_ON
    assert lightener.brightness == 120


###########################################################
### LightenerLightEntity class only tests


async def test_lightener_light_entity_properties(hass):
    """Test all the basic properties of the LightenerLight class"""

    config = {"friendly_name": "Living Room"}
    unique_id = str(uuid4())

    lightener = LightenerLight(hass, config, unique_id)

    light = LightenerLightEntity(
        hass, lightener, "light.test1", {"brightness": {"10": "20"}}
    )

    assert light.entity_id == "light.test1"
    assert light.state == "off"


@pytest.mark.skip(reason="I have no idea how to run this test :(")
async def test_lightener_light_entity_turn_on(hass: HomeAssistant):
    """Test the turn on of LightenerLightEntity"""

    config = {"friendly_name": "Living Room"}

    lightener = LightenerLight(hass, config, str(uuid4()))

    light = LightenerLightEntity(
        hass, lightener, "light.test1", {"brightness": {"50": "100"}}
    )

    lightener_brightness = _convert_percent_to_brightness(25)
    await light.async_turn_on(lightener_brightness)

    state = hass.states.get(light.entity_id)
    assert state.state == STATE_ON
    assert state.attributes[ATTR_BRIGHTNESS] == lightener_brightness * 2


###########################################################
### LightenerLightEntity class only tests


def test_convert_percent_to_brightness():
    """Test the _convert_percent_to_brightness function"""

    assert _convert_percent_to_brightness(0) == 0
    assert _convert_percent_to_brightness(10) == 25
    assert _convert_percent_to_brightness(100) == 255
