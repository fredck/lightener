"""Platform for Lightener lights."""

from __future__ import annotations

import logging
from math import ceil
from typing import Any

import voluptuous as vol

from homeassistant import core
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ENTITY_ID_FORMAT,
    ColorMode,
    LightEntity,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_ENTITY_ID,
    CONF_FRIENDLY_NAME,
    CONF_LIGHTS,
    CONF_NAME,
    CONF_UNIQUE_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.core import HomeAssistant, State

# Import the device class from the component that you want to support
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.config_validation import PLATFORM_SCHEMA
from homeassistant.helpers.entity import async_generate_entity_id
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import (
    async_track_state_change,
    async_track_state_change_event,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.loader import bind_hass


_LOGGER = logging.getLogger(__name__)

ENTITY_SCHEMA = vol.All({vol.Clamp(min=1, max=50): vol.Clamp(min=0, max=70)})

LIGHT_SCHEMA = vol.All(
    vol.Schema(
        {
            vol.Required("entities"): {cv.entity_id: ENTITY_SCHEMA},
            vol.Optional(CONF_FRIENDLY_NAME): cv.string,
        }
    ),
)

PLATFORM_SCHEMA = vol.All(
    PLATFORM_SCHEMA.extend(
        {vol.Required(CONF_LIGHTS): cv.schema_with_slug_keys(LIGHT_SCHEMA)}
    ),
)


def _convert_percent_to_brightness(percent: int) -> int:
    return int(255 * percent / 100)


async def _async_create_entities(hass: HomeAssistant, config):
    lights = []

    for object_id, entity_config in config[CONF_LIGHTS].items():
        lights.append(LightenerLight(hass, object_id, entity_config))

    return lights


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the template lights."""
    async_add_entities(await _async_create_entities(hass, config))


class LightenerLight(LightEntity):
    """Represents a Lightener light."""

    def __init__(self, hass: HomeAssistant, object_id: str, config) -> None:
        """Initialize the light."""

        self._hass = hass

        # The unique id of the light is the one set in the configuration.
        self._unique_id = object_id

        # Setup the id for this light. E.g. "light.living_room" if config has "living_room".
        self.entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT, object_id, hass=hass
        )

        # Define the display name of the light.
        self._name = config.get(CONF_FRIENDLY_NAME)

        self._state = "off"
        self._brightness = 255

        ## Add all entities that are managed by this lightened.

        entities = []

        for entity_id, entity_config in config["entities"].items():
            entities.append(LightenerLightEntity(hass, entity_id, entity_config))

        self._entities = entities

    @property
    def should_poll(self) -> bool:
        return False

    @property
    def unique_id(self) -> str | None:
        return self._unique_id

    @property
    def name(self) -> str:
        """Return the display name of this light."""
        return self._name

    @property
    def color_mode(self) -> str:
        """Return the color mode of the light."""

        # A lightened supports brightenes control only.
        return ColorMode.BRIGHTNESS

    @property
    def supported_color_modes(self) -> set[str] | None:
        """Flag supported color modes."""
        return {self.color_mode}

    @property
    def icon(self) -> str | None:
        return "mdi:lightbulb-group"

    @property
    def is_on(self) -> bool | None:
        """Return true if light is on."""
        return None if self._state is None else self._state == "on"

    @property
    def brightness(self) -> int | None:
        return self._brightness

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the lights on."""

        self._state = "on"
        self._brightness = dict(kwargs).get("brightness") or self._brightness
        self.async_schedule_update_ha_state(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the lights off."""

        self._state = "off"
        self.async_schedule_update_ha_state()

    async def async_added_to_hass(self) -> None:
        async_track_state_change(self._hass, self.entity_id, self._async_state_change)

    async def _async_state_change(self, entity_id, old_state, new_state: State) -> None:
        # Update brightness with the event value.
        self._brightness = new_state.attributes.get("brightness") or self._brightness

        if new_state.state == "on":
            for entity in self._entities:
                await entity.async_turn_on(self._brightness)

        else:
            for entity in self._entities:
                await entity.async_turn_off()


class LightenerLightEntity:
    """Represents a light entity managed by a LightnerLight."""

    def __init__(
        self: LightenerLightEntity, hass: HomeAssistant, entity_id: str, config: dict
    ) -> None:
        self._id = entity_id
        self._hass = hass

        config_levels = {}

        for lightener_level, entity_value in config.items():
            config_levels[
                _convert_percent_to_brightness(lightener_level)
            ] = _convert_percent_to_brightness(entity_value)

        config_levels.setdefault(255, 255)

        # Start the level list with value 0 for level 0.
        levels = [0]

        previous = 0

        # Fill all levels with the calculated values between the ranges.
        for level in sorted(config_levels.keys()):
            previous_level = 0 if previous == 0 else config_levels.get(previous)
            step = (config_levels.get(level) - previous_level) / (level - previous)
            for i in range(previous + 1, level + 1):
                value_at_current_level = int(step * (i - previous) + previous_level)
                levels.append(value_at_current_level)
            previous = level

        self._levels = levels

    @property
    def brightness(self) -> int | None:
        """Return the brightness of the light."""

        state = self._hass.states.get(self._id).as_dict()

        brightness = state.get("attributes").get("brightness") or 0

        return 100 if brightness == 255 else ceil(brightness / 255 * 99.0)

    async def async_turn_on(self: LightenerLightEntity, brightness: int) -> None:
        """Turns the light on or off, according to the lightened configuration for the given brighteness."""
        self._hass.async_create_task(
            self._hass.services.async_call(
                core.DOMAIN,
                SERVICE_TURN_ON,
                {ATTR_ENTITY_ID: self._id, "brightness": self._levels[brightness]},
                blocking=True,
            )
        )

    async def async_turn_off(self: LightenerLightEntity) -> None:
        """Turn the light off."""

        self._hass.async_create_task(
            self._hass.services.async_call(
                core.DOMAIN,
                SERVICE_TURN_OFF,
                {ATTR_ENTITY_ID: self._id},
                blocking=True,
            )
        )
