"""Platform for Lightener lights."""

from __future__ import annotations

import logging
from typing import Any, Literal

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
    CONF_ENTITIES,
    CONF_FRIENDLY_NAME,
    CONF_LIGHTS,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import Context, HomeAssistant, State
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.config_validation import PLATFORM_SCHEMA
from homeassistant.helpers.entity import async_generate_entity_id
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import Event, async_track_state_change_event
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
import homeassistant.util.ulid as ulid_util

_LOGGER = logging.getLogger(__name__)

ENTITY_SCHEMA = vol.All(
    vol.DefaultTo({1: 1, 100: 100}),
    {
        vol.All(vol.Coerce(int), vol.Range(min=1, max=100)): vol.All(
            vol.Coerce(int), vol.Range(min=0, max=100)
        )
    },
)

LIGHT_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ENTITIES): {cv.entity_id: ENTITY_SCHEMA},
        vol.Optional(CONF_FRIENDLY_NAME): cv.string,
    }
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_LIGHTS): cv.schema_with_slug_keys(LIGHT_SCHEMA)}
)

LIGHTENER_CONTEXT = ulid_util.ulid()


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

        self._state = STATE_OFF
        self._brightness = 255

        ## Add all entities that are managed by this lightened.

        entities = []

        for entity_id, entity_config in config[CONF_ENTITIES].items():
            entities.append(LightenerLightEntity(hass, self, entity_id, entity_config))

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
        return None if self._state is None else self._state == STATE_ON

    @property
    def brightness(self) -> int | None:
        return self._brightness

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the lights on."""

        self._state = STATE_ON
        self._brightness = dict(kwargs).get(ATTR_BRIGHTNESS) or self._brightness
        self.async_schedule_update_ha_state(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the lights off."""

        self._state = STATE_OFF
        self.async_schedule_update_ha_state()

    async def async_added_to_hass(self) -> None:
        async def _async_state_change(ev: Event) -> None:
            # Do nothing if the change has been triggered when a child entity was changed directly.
            if ev.context.id == LIGHTENER_CONTEXT:
                return

            new_state: State = ev.data.get("new_state")

            # Update brightness with the event value.
            self._brightness = (
                new_state.attributes.get(ATTR_BRIGHTNESS) or self._brightness
            )

            if new_state.state == STATE_ON:
                for entity in self._entities:
                    await entity.async_turn_on(self._brightness)

            else:
                for entity in self._entities:
                    await entity.async_turn_off()

        async_track_state_change_event(self._hass, self.entity_id, _async_state_change)

        # Track state changes of the child entities and update the lightener state accordingly.

        async def _async_child_state_change(ev: Event) -> None:
            # Do nothing if the change has been triggered by the lightener.
            if ev.context.id == LIGHTENER_CONTEXT:
                return

            service_to_call = SERVICE_TURN_OFF

            if any(entity.state == STATE_ON for entity in self._entities):
                service_to_call = SERVICE_TURN_ON

            self._hass.async_create_task(
                self._hass.services.async_call(
                    core.DOMAIN,
                    service_to_call,
                    {ATTR_ENTITY_ID: self.entity_id},
                    blocking=True,
                    context=Context(None, None, LIGHTENER_CONTEXT),
                )
            )

        async_track_state_change_event(
            self._hass,
            map(lambda e: e.entity_id, self._entities),
            _async_child_state_change,
        )


class LightenerLightEntity:
    """Represents a light entity managed by a LightnerLight."""

    def __init__(
        self: LightenerLightEntity,
        hass: HomeAssistant,
        parent: LightenerLight,
        entity_id: str,
        config: dict,
    ) -> None:
        self._entity_id = entity_id
        self._hass = hass
        self._parent = parent

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
    def entity_id(self: LightenerLightEntity) -> str:
        """The original entity id of this managed entity."""

        return self._entity_id

    @property
    def state(self: LightenerLightEntity) -> Literal["on", "off"] | None:
        """The current state of this entity."""

        entity_state = self._hass.states.get(self._entity_id)

        if entity_state is None:
            return None

        return entity_state.state

    async def async_turn_on(self: LightenerLightEntity, brightness: int) -> None:
        """Turns the light on or off, according to the lightened configuration for the given brighteness."""

        self._hass.async_create_task(
            self._hass.services.async_call(
                core.DOMAIN,
                SERVICE_TURN_ON,
                {
                    ATTR_ENTITY_ID: self._entity_id,
                    ATTR_BRIGHTNESS: self._levels[brightness],
                },
                blocking=True,
                context=Context(None, None, LIGHTENER_CONTEXT),
            )
        )

    async def async_turn_off(self: LightenerLightEntity) -> None:
        """Turn the light off."""

        self._hass.async_create_task(
            self._hass.services.async_call(
                core.DOMAIN,
                SERVICE_TURN_OFF,
                {ATTR_ENTITY_ID: self._entity_id},
                blocking=True,
                context=Context(None, None, LIGHTENER_CONTEXT),
            )
        )
