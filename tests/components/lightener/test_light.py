"""Tests for the light platform"""

from unittest.mock import ANY, Mock, patch
from uuid import uuid4

from homeassistant.components.light import ATTR_BRIGHTNESS
from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.components.light import ColorMode
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant

from custom_components.lightener.light import (
    LightenerLight,
    LightenerLightEntity,
    _convert_percent_to_brightness,
    async_setup_platform,
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


async def test_lightener_light_cross_controll(hass: HomeAssistant):
    """Test Lightener controlling other Lighteners"""

    lightener1 = LightenerLight(
        hass,
        {
            "friendly_name": "Lightener1",
            "entities": {
                "light.test1": {"brightness": {}},
                "light.test2": {"brightness": {}},
            },
        },
    )
    await lightener1.async_added_to_hass()

    lightener2 = LightenerLight(
        hass,
        {
            "friendly_name": "Lightener2",
            "entities": {
                "light.test1": {"brightness": {}},
                "light.lightener1": {"brightness": {}},
            },
        },
    )
    await lightener2.async_added_to_hass()

    lightener3 = LightenerLight(
        hass,
        {
            "friendly_name": "Lightener3",
            "entities": {
                "light.lightener1": {"brightness": {}},
                "light.lightener2": {"brightness": {}},
            },
        },
    )
    await lightener3.async_added_to_hass()

    await lightener1.async_turn_off()
    await lightener2.async_turn_off()
    await lightener3.async_turn_off()

    await hass.async_block_till_done()

    with patch.object(hass.services, "async_call") as async_call_mock:
        await lightener1.async_turn_on()
        await hass.async_block_till_done()

    # [0] -> light.test1 for light.lightener1
    # [1] -> light.test2 for light.lightener1
    # [2] -> light.test1 for light.lightener2
    # [3] -> light.lightener1 from for light.lightener3
    assert async_call_mock.call_count == 4

    assert async_call_mock.mock_calls[0].args[2]["entity_id"] == "light.test1"
    assert async_call_mock.mock_calls[1].args[2]["entity_id"] == "light.test2"
    assert async_call_mock.mock_calls[2].args[2]["entity_id"] == "light.lightener2"
    assert async_call_mock.mock_calls[3].args[2]["entity_id"] == "light.lightener3"

async def test_lightener_light_cross_controll2(hass: HomeAssistant):
    """Test Lightener controlling other Lighteners"""

    lightener1 = LightenerLight(
        hass,
        {
            "friendly_name": "Lightener1",
            "entities": {
                "light.test1": {"brightness": {}},
                "light.test2": {"brightness": {}},
            },
        },
    )
    await lightener1.async_added_to_hass()

    lightener2 = LightenerLight(
        hass,
        {
            "friendly_name": "Lightener2",
            "entities": {
                "light.test1": {"brightness": {}},
                "light.lightener1": {"brightness": {}},
            },
        },
    )
    await lightener2.async_added_to_hass()

    lightener3 = LightenerLight(
        hass,
        {
            "friendly_name": "Lightener3",
            "entities": {
                "light.lightener1": {"brightness": {}},
                "light.lightener2": {"brightness": {}},
            },
        },
    )
    await lightener3.async_added_to_hass()

    await lightener1.async_turn_off()
    await lightener2.async_turn_off()
    await lightener3.async_turn_off()

    await hass.async_block_till_done()

    with patch.object(hass.services, "async_call") as async_call_mock:
        await lightener2.async_turn_on()
        await hass.async_block_till_done()

    # assert async_call_mock.call_count == 4

    assert async_call_mock.mock_calls[0].args[2]["entity_id"] == "light.test1"
    assert async_call_mock.mock_calls[1].args[2]["entity_id"] == "light.lightener1"
    assert async_call_mock.mock_calls[2].args[2]["entity_id"] == "light.lightener3"
    # assert async_call_mock.mock_calls[3].args[2]["entity_id"] == "light.test2"

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


async def test_lightener_light_entity_calculated_levels(hass):
    """Test the calculation of brigthness levels"""

    # pylint: disable=W0212

    config = {"friendly_name": "Living Room"}
    unique_id = str(uuid4())

    lightener = LightenerLight(hass, config, unique_id)

    light = LightenerLightEntity(
        hass,
        lightener,
        "light.test1",
        {
            "brightness": {
                "10": "100",
            }
        },
    )

    assert light._levels[0] == 0
    assert light._levels[13] == 128
    assert light._levels[25] == 246
    assert light._levels[26] == 255
    assert light._levels[27] == 255
    assert light._levels[100] == 255
    assert light._levels[255] == 255

    light = LightenerLightEntity(
        hass,
        lightener,
        "light.test1",
        {
            "brightness": {
                "100": "0",  # Test the ordering
                "10": "10",
                "50": "100",
            }
        },
    )

    assert light._levels[0] == 0
    assert light._levels[15] == 15
    assert light._levels[26] == 26
    assert light._levels[27] == 29
    assert light._levels[128] == 255
    assert light._levels[129] == 253
    assert light._levels[255] == 0


async def test_lightener_light_entity_turn_on(hass: HomeAssistant):
    """Test the turn on of LightenerLightEntity"""

    config = {"friendly_name": "Living Room"}

    lightener = LightenerLight(hass, config, str(uuid4()))

    light = LightenerLightEntity(
        hass, lightener, "light.test1", {"brightness": {"50": "100"}}
    )

    with patch.object(hass.services, "async_call") as async_call_mock:
        await light.async_turn_on(_convert_percent_to_brightness(25))

    async_call_mock.assert_called_once_with(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: "light.test1",
            ATTR_BRIGHTNESS: _convert_percent_to_brightness(50),
        },
        blocking=True,
        context=ANY,
    )


async def test_lightener_light_entity_turn_off(hass: HomeAssistant):
    """Test the turn on of LightenerLightEntity"""

    config = {"friendly_name": "Living Room"}

    lightener = LightenerLight(hass, config, str(uuid4()))

    light = LightenerLightEntity(
        hass, lightener, "light.test1", {"brightness": {"50": "100"}}
    )

    with patch.object(hass.services, "async_call") as async_call_mock:
        await light.async_turn_off()

    async_call_mock.assert_called_once_with(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "light.test1"},
        blocking=True,
        context=ANY,
    )


###########################################################
### Other


def test_convert_percent_to_brightness():
    """Test the _convert_percent_to_brightness function"""

    assert _convert_percent_to_brightness(0) == 0
    assert _convert_percent_to_brightness(10) == 26
    assert _convert_percent_to_brightness(100) == 255


async def test_async_setup_platform(hass):
    """Test for platform setup"""

    # pylint: disable=W0212

    async_add_entities_mock = Mock()

    config = {
        "platform": "lightener",
        "lights": {
            "lightener_1": {
                "friendly_name": "Lightener 1",
                "entities": {"light.test1": {10: 100}},
            },
            "lightener_2": {
                "friendly_name": "Lightener 2",
                "entities": {"light.test2": {100: 10}},
            },
        },
    }

    await async_setup_platform(hass, config, async_add_entities_mock)

    assert async_add_entities_mock.call_count == 1

    created_lights: list = async_add_entities_mock.call_args.args[0]

    assert len(created_lights) == 2

    light: LightenerLight = created_lights[0]

    assert isinstance(light, LightenerLight)
    assert light.entity_id == "light.lightener_1"
    assert light.name == "Lightener 1"
    assert len(light._entities) == 1

    controlled_light: LightenerLightEntity = light._entities[0]

    assert isinstance(controlled_light, LightenerLightEntity)
    assert controlled_light.entity_id == "light.test1"
    assert controlled_light._levels[26] == 255

    light: LightenerLight = created_lights[1]

    assert isinstance(light, LightenerLight)
    assert light.entity_id == "light.lightener_2"
    assert light.name == "Lightener 2"
    assert len(light._entities) == 1

    controlled_light: LightenerLightEntity = light._entities[0]

    assert isinstance(controlled_light, LightenerLightEntity)
    assert controlled_light.entity_id == "light.test2"
    assert controlled_light._levels[255] == 26
