"""Tests for the light platform"""

from unittest.mock import ANY, Mock, patch
from uuid import uuid4

import pytest
from homeassistant.components.light import ATTR_TRANSITION, ColorMode
from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_OFF, SERVICE_TURN_ON
from homeassistant.core import HomeAssistant, ServiceRegistry

from custom_components.lightener.const import TYPE_DIMMABLE, TYPE_ONOFF
from custom_components.lightener.light import (
    LightenerControlledLight,
    LightenerLight,
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

    # Name must be empty so it'll be taken from the device
    assert lightener.name is None
    assert lightener.device_info["name"] == "Living Room"

    assert lightener.should_poll is False
    assert lightener.has_entity_name is True

    assert lightener.icon == "mdi:lightbulb-group"


async def test_lightener_light_properties_no_unique_id(hass):
    """Test all the basic properties of the LightenerLight class when no unique id is provided"""

    config = {"friendly_name": "Living Room"}

    lightener = LightenerLight(hass, config)

    assert lightener.unique_id is None
    assert lightener.device_info is None
    assert lightener.name == "Living Room"


async def test_lightener_light_turn_on(hass: HomeAssistant, create_lightener):
    """Test the state changes of the LightenerLight class when turned on"""

    lightener: LightenerLight = await create_lightener(
        config={
            "friendly_name": "Test",
            "entities": {
                "light.test1": {},
                "light.test2": {},
            },
        }
    )

    await lightener.async_turn_on()
    await hass.async_block_till_done()

    assert hass.states.get("light.test1").state == "on"
    assert hass.states.get("light.test2").state == "on"


async def test_lightener_light_turn_on_forward(hass: HomeAssistant, create_lightener):
    """Test if passed arguments are forwared when turned on"""

    lightener: LightenerLight = await create_lightener()

    with patch.object(ServiceRegistry, "async_call") as async_call_mock:
        await lightener.async_turn_on(
            brightness=50, effect="blink", color_temp_kelvin=3000
        )

    async_call_mock.assert_called_once_with(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: "light.test1",
            "brightness": 50,
            "effect": "blink",
            "color_temp_kelvin": 3000,
        },
        blocking=True,
        context=ANY,
    )


async def test_lightener_light_turn_on_go_off_if_brightness_0(
    hass: HomeAssistant, create_lightener
):
    """Test that turned on sends brightness 0 if the controlled light is on"""

    lightener: LightenerLight = await create_lightener(
        config={
            "friendly_name": "Test",
            "entities": {"light.test1": {"50": "0"}},
        }
    )

    hass.states.async_set(entity_id="light.test1", new_state="on")

    await lightener.async_turn_on(brightness=1)
    await hass.async_block_till_done()

    assert hass.states.get("light.test1").state == "off"


async def test_lightener_light_turn_on_translate_brightness(
    hass: HomeAssistant, create_lightener
):
    """Test that turned on sends brightness 0 if the controlled light is on"""

    lightener: LightenerLight = await create_lightener(
        config={
            "friendly_name": "Test",
            "entities": {"light.test1": {"50": "0"}},
        }
    )
    hass.states.async_set(entity_id="light.test1", new_state="on")

    await lightener.async_turn_on(brightness=192)
    await hass.async_block_till_done()

    assert hass.states.get("light.test1").state == "on"
    assert hass.states.get("light.test1").attributes["brightness"] == 129


async def test_lightener_light_turn_on_go_off_if_brightness_0_transition(
    hass: HomeAssistant, create_lightener
):
    """Test that turned on sends brightness 0 if the controlled light is on"""

    lightener: LightenerLight = await create_lightener(
        config={
            "friendly_name": "Test",
            "entities": {"light.test1": {"50": "0"}},
        }
    )

    hass.states.async_set(entity_id="light.test1", new_state="on")

    with patch.object(ServiceRegistry, "async_call") as async_call_mock:
        await lightener.async_turn_on(brightness=1, transition=10)

    async_call_mock.assert_called_once_with(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "light.test1", ATTR_TRANSITION: 10},
        blocking=True,
        context=ANY,
    )


async def test_lightener_light_async_update_group_state(
    hass: HomeAssistant, create_lightener
):
    """Test that turned on does nothing if the controlled light is already off"""

    lightener: LightenerLight = await create_lightener(
        config={
            "friendly_name": "Test",
            "entities": {"light.test1": {"50": "0"}},
        }
    )

    lightener._attr_brightness = 150  # pylint: disable=protected-access

    hass.states.async_set(
        entity_id="light.test1", new_state="on", attributes={"color_temp_kelvin": 3000}
    )

    lightener.async_update_group_state()

    assert lightener.is_on is True
    assert lightener.color_temp_kelvin == 3000

    assert lightener.brightness == 255

    hass.states.async_set(
        entity_id="light.test1", new_state="on", attributes={"brightness": 255}
    )

    lightener.async_update_group_state()

    assert lightener.brightness == 255

    hass.states.async_set(
        entity_id="light.test1", new_state="on", attributes={"brightness": 1}
    )

    lightener.async_update_group_state()

    assert lightener.brightness == 129

    hass.states.async_set(
        entity_id="light.test1", new_state="on", attributes={"brightness": 0}
    )

    lightener.async_update_group_state()

    assert lightener.is_on is True
    assert lightener.brightness == 1


async def test_lightener_light_async_update_group_state_zero(
    hass: HomeAssistant, create_lightener
):
    """Test that turned on does nothing if the controlled light is already off"""

    lightener: LightenerLight = await create_lightener(
        config={
            "friendly_name": "Test",
            "entities": {"light.test1": {}},
        }
    )

    lightener._attr_brightness = 150  # pylint: disable=protected-access

    hass.states.async_set(
        entity_id="light.test1", new_state="on", attributes={"brightness": 0}
    )

    lightener.async_update_group_state()

    assert lightener.brightness == 0


async def test_lightener_light_async_update_group_state_unavailable(
    hass: HomeAssistant, create_lightener
):
    """Test that turned on does nothing if the controlled light is already off"""

    lightener: LightenerLight = await create_lightener(
        config={
            "friendly_name": "Test",
            "entities": {"light.test1": {"50": "0"}, "light.I_DONT_EXIST": {}},
        }
    )

    lightener._attr_brightness = 150  # pylint: disable=protected-access

    hass.states.async_set(
        entity_id="light.test1", new_state="on", attributes={"brightness": 1}
    )

    lightener.async_update_group_state()

    assert lightener.brightness == 129


async def test_lightener_light_async_update_group_state_no_match_no_change(
    hass: HomeAssistant, create_lightener
):
    """Test that turned on does nothing if the controlled light is already off"""

    lightener: LightenerLight = await create_lightener(
        config={
            "friendly_name": "Test",
            "entities": {"light.test1": {"50": "0"}, "light.test2": {"10": "100"}},
        }
    )

    def test(test1: int, test2: int, result: int):
        lightener._attr_brightness = 150  # pylint: disable=protected-access

        hass.states.async_set(
            entity_id="light.test1", new_state="on", attributes={"brightness": test1}
        )

        hass.states.async_set(
            entity_id="light.test2", new_state="on", attributes={"brightness": test2}
        )

        lightener.async_update_group_state()

        assert lightener.brightness == result

    # Matches
    test(0, 26, 3)
    test(1, 255, 129)

    # No matches
    test(129, 1, 150)
    test(1, 254, 150)
    test(1, 1, 150)
    test(1, None, 150)


@pytest.mark.parametrize(
    "test1, current, result",
    [
        (0, 10, 10),
        (0, 20, 20),
        # We're in the range, so the change must happen here.
        (128, 20, 141),
        (255, 200, 200),
        (255, 255, 255),
    ],
)
async def test_lightener_light_async_update_group_state_current_good_no_change(
    test1, current, result, hass: HomeAssistant, create_lightener
):
    """Test that turned on does nothing if the controlled light is already off"""

    lightener: LightenerLight = await create_lightener(
        config={
            "friendly_name": "Test",
            "entities": {"light.test1": {"50": "0", "60": "100"}},
        }
    )

    lightener._attr_brightness = current  # pylint: disable=protected-access

    hass.states.async_set(
        entity_id="light.test1", new_state="on", attributes={"brightness": test1}
    )

    lightener.async_update_group_state()

    assert lightener.brightness == result


async def test_lightener_light_async_update_group_state_onoff(
    hass: HomeAssistant, create_lightener
):
    """Test that turned on does nothing if the controlled light is already off"""

    lightener: LightenerLight = await create_lightener(
        config={
            "friendly_name": "Test",
            "entities": {"light.test_onoff": {}},
        }
    )

    # lightener._attr_brightness = 150    # pylint: disable=protected-access

    hass.states.async_set(
        entity_id="light.test_onoff",
        new_state="on",
        attributes={"color_mode": ColorMode.ONOFF},
    )

    lightener.async_update_group_state()

    assert lightener.color_mode == ColorMode.BRIGHTNESS
    assert lightener.supported_color_modes == {ColorMode.BRIGHTNESS}


###########################################################
### LightenerControlledLight class only tests


async def test_lightener_light_entity_properties(hass):
    """Test all the basic properties of the LightenerLight class"""

    light = LightenerControlledLight("light.test1", {"brightness": {"10": "20"}}, hass)

    assert light.entity_id == "light.test1"


async def test_lightener_light_entity_calculated_levels(hass):
    """Test the calculation of brigthness levels"""

    light = LightenerControlledLight(
        "light.test1",
        {
            "brightness": {
                "10": "100",
            }
        },
        hass,
    )

    assert light.levels[0] == 0
    assert light.levels[13] == 128
    assert light.levels[25] == 246
    assert light.levels[26] == 255
    assert light.levels[27] == 255
    assert light.levels[100] == 255
    assert light.levels[255] == 255

    light = LightenerControlledLight(
        "light.test1",
        {
            "brightness": {
                "100": "0",  # Test the ordering
                "10": "10",
                "50": "100",
            }
        },
        hass,
    )

    assert light.levels[0] == 0
    assert light.levels[15] == 15
    assert light.levels[26] == 26
    assert light.levels[27] == 29
    assert light.levels[128] == 255
    assert light.levels[129] == 253
    assert light.levels[255] == 0


async def test_lightener_light_entity_calculated_to_lightner_levels(hass):
    """Test the calculation of brigthness levels"""

    light = LightenerControlledLight(
        "light.test1",
        {
            "brightness": {
                "10": "100"  # 26: 255
            }
        },
        hass,
    )

    assert light.to_lightener_levels[0] == [0]
    assert light.to_lightener_levels[26] == [3]
    assert light.to_lightener_levels[253] == [26]
    assert light.to_lightener_levels[254] == [26]
    assert light.to_lightener_levels[255] == list(range(26, 256))

    light = LightenerControlledLight(
        "light.test1",
        {
            "brightness": {
                "100": "0",  # Test the ordering
                "10": "10",
                "50": "100",
            }
        },
        hass,
    )

    assert light.to_lightener_levels[0] == [0, 255]
    assert light.to_lightener_levels[26] == [26, 243]
    assert light.to_lightener_levels[255] == [128]

    assert light.to_lightener_levels[3] == [3, 254]
    assert light.to_lightener_levels[10] == [10, 251]


@pytest.mark.parametrize(
    "entity_id, expected_type",
    [
        ("light.test1", TYPE_DIMMABLE),
        ("light.test_onoff", TYPE_ONOFF),
    ],
)
async def test_lightener_light_entity_type(entity_id, expected_type, hass):
    """Test translate_brightness_back with float values"""

    light = LightenerControlledLight(
        entity_id,
        {},
        hass,
    )

    assert light.type is expected_type


@pytest.mark.parametrize(
    "lightener_level, light_level",
    [
        (0, 0),
        (1, 10),
        (26, 255),
        (39, 123),
        (255, 0),
    ],
)
async def test_lightener_light_entity_translate_brightness_dimmable(
    lightener_level, light_level, hass
):
    """Test translate_brightness_back with float values"""

    light = LightenerControlledLight(
        "light.test1",
        {"brightness": {"10": "100", "20": "0", "100": "0"}},
        hass,
    )

    assert light.translate_brightness(lightener_level) == light_level


@pytest.mark.parametrize(
    "lightener_level, light_level",
    [
        (0, 0),
        (1, 255),
        (26, 255),
        (39, 255),
        (255, 0),
    ],
)
async def test_lightener_light_entity_translate_brightness_dimmable_onoff(
    lightener_level, light_level, hass
):
    """Test translate_brightness_back with float values"""

    light = LightenerControlledLight(
        "light.test_onoff",
        {"brightness": {"10": "100", "20": "0", "100": "0"}},
        hass,
    )

    assert light.translate_brightness(lightener_level) == light_level


async def test_lightener_light_entity_translate_brightness_float(hass):
    """Test translate_brightness_back with float values"""

    light = LightenerControlledLight(
        "light.test1",
        {
            "brightness": {
                "10": "100"  # 26: 255
            }
        },
        hass,
    )

    assert light.translate_brightness(2.9) == 20


async def test_lightener_light_entity_translate_brightness_back_float(hass):
    """Test translate_brightness_back with float values"""

    light = LightenerControlledLight(
        "light.test1",
        {
            "brightness": {
                "10": "100"  # 26: 255
            }
        },
        hass,
    )

    assert light.translate_brightness_back(25.9) == [3]


###########################################################
### Other


@pytest.mark.parametrize(
    "percent, brightness",
    [
        (0, 0),
        (10, 26),
        (100, 255),
    ],
)
def test_convert_percent_to_brightness(percent, brightness):
    """Test the _convert_percent_to_brightness function"""

    assert _convert_percent_to_brightness(percent) == brightness


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
    assert light.name == "Lightener 1"
    assert len(light._entities) == 1

    controlled_light: LightenerControlledLight = light._entities[0]

    assert isinstance(controlled_light, LightenerControlledLight)
    assert controlled_light.entity_id == "light.test1"
    assert controlled_light.levels[26] == 255

    light: LightenerLight = created_lights[1]

    assert isinstance(light, LightenerLight)
    assert light.name == "Lightener 2"
    assert len(light._entities) == 1

    controlled_light: LightenerControlledLight = light._entities[0]

    assert isinstance(controlled_light, LightenerControlledLight)
    assert light.extra_state_attributes["entity_id"][0] == "light.test2"
    assert controlled_light.entity_id == "light.test2"
    assert controlled_light.levels[255] == 26


# Issues


async def test_lightener_issue_41(hass: HomeAssistant, create_lightener):
    """Test the state changes of the LightenerLight class when turned on"""

    lightener: LightenerLight = await create_lightener(
        config={
            "friendly_name": "Test",
            "entities": {
                "light.test1": {},
                "light.test2": {50: 0},
            },
        }
    )

    await lightener.async_turn_on(brightness=30)
    await hass.async_block_till_done()
    assert lightener.brightness == 30

    await lightener.async_turn_off()
    await hass.async_block_till_done()
    assert lightener.brightness == 30
    assert hass.states.get("light.test1").state == "off"
    assert hass.states.get("light.test2").state == "off"

    await lightener.async_turn_on()
    await hass.async_block_till_done()
    assert lightener.brightness == 30

    assert hass.states.get("light.test1").state == "on"
    assert hass.states.get("light.test1").attributes["brightness"] == 30
    assert hass.states.get("light.test2").state == "off"


async def test_lightener_issue_97(hass: HomeAssistant, create_lightener):
    """Test the state changes of the LightenerLight class when turned on"""

    lightener: LightenerLight = await create_lightener(
        config={
            "friendly_name": "Test",
            "entities": {
                "light.test1": {50: 100},
                "light.test_onoff": {50: 0},
            },
        }
    )

    await lightener.async_turn_on(brightness=129)  # 51% of 255
    await hass.async_block_till_done()
    assert lightener.brightness == 129
    assert hass.states.get("light.test").attributes["brightness"] == 129

    assert hass.states.get("light.test1").state == "on"
    assert hass.states.get("light.test_onoff").state == "on"

    await lightener.async_turn_on(brightness=200)
    await hass.async_block_till_done()
    assert lightener.brightness == 200
    assert hass.states.get("light.test").attributes["brightness"] == 200

    assert hass.states.get("light.test1").state == "on"
    assert hass.states.get("light.test_onoff").state == "on"

    assert hass.states.get("light.test1").attributes["brightness"] == 255
