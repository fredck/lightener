"""Platform for Lightener lights."""

from __future__ import annotations

import logging
import math
from collections import OrderedDict
from types import MappingProxyType
from typing import Any

import homeassistant.helpers.config_validation as cv
import homeassistant.util.ulid as ulid_util
import voluptuous as vol
from homeassistant.components.group.light import (FORWARDED_ATTRIBUTES,
                                                  LightGroup)
from homeassistant.components.light import ATTR_BRIGHTNESS
from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (ATTR_ENTITY_ID, CONF_ENTITIES,
                                 CONF_FRIENDLY_NAME, CONF_LIGHTS,
                                 SERVICE_TURN_ON, STATE_OFF, STATE_ON)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.config_validation import PLATFORM_SCHEMA
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import async_migrate_entry
from .const import DOMAIN

SIDE_EFFECT_CONTEXT_ID = ulid_util.ulid()

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


def _convert_percent_to_brightness(percent: int) -> int:
    return math.ceil(255 * percent / 100)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Setup entities for config entries."""
    unique_id = config_entry.entry_id

    await async_migrate_entry(hass, config_entry)

    # The unique id of the light will simply match the config entry ID.
    async_add_entities([LightenerLight(config_entry.data, unique_id)])


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up entities for configuration.yaml entries."""

    lights = []

    for object_id, entity_config in config[CONF_LIGHTS].items():
        entry = ConfigEntry(1, DOMAIN, "", entity_config, "user")

        await async_migrate_entry(hass, entry, False)

        data = dict(entry.data)
        data["entity_id"] = object_id

        lights.append(LightenerLight(data))

    async_add_entities(lights)


class LightenerLight(LightGroup):
    """Represents a Lightener light."""

    def __init__(
        self,
        config_data: MappingProxyType,
        unique_id: str | None = None,
    ) -> None:
        """Initialize the light using the config entry information."""

        ## Add all entities that are managed by this lightened.
        entities: list[LightenerControlledLight] = []
        entity_ids: list[str] = []

        if config_data.get(CONF_ENTITIES) is not None:
            for entity_id, entity_config in config_data[CONF_ENTITIES].items():
                entity_ids.append(entity_id)
                entities.append(
                    LightenerControlledLight(entity_id, entity_config)
                )

        super().__init__(
            unique_id=unique_id,
            name=config_data[CONF_FRIENDLY_NAME] if unique_id is None else None,
            entity_ids=entity_ids,
            mode=None
        )

        self._attr_has_entity_name = unique_id is not None

        if self._attr_has_entity_name:
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, self.unique_id)},
                name=config_data[CONF_FRIENDLY_NAME]
            )

        self._entities = entities

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Forward the turn_on command to all controlled lights."""

        # This is basically a copy of LightGroup::async_turn_on but it has been changed
        # so we can pass different brightness to each light.

        # List all attributes we want to forward.
        data = {
            key: value for key, value in kwargs.items() if key in FORWARDED_ATTRIBUTES
        }

        # Retrieve the brightness being set to the Lightener (or current level if not setting it)
        brightness = kwargs.get(ATTR_BRIGHTNESS) or self.brightness

        for entity in self._entities:
            # Add entity specific attributes.
            entity_data = data.copy()
            entity_data[ATTR_ENTITY_ID] = entity.entity_id

            if brightness is not None:
                entity_data[ATTR_BRIGHTNESS] = entity.translate_brightness(brightness)

            if entity_data.get(ATTR_BRIGHTNESS) == 0:
                current_state = self.hass.states.get(entity.entity_id)

                if current_state is not None and current_state.state == STATE_OFF:
                    continue

            await self.hass.services.async_call(
                LIGHT_DOMAIN,
                SERVICE_TURN_ON,
                entity_data,
                blocking=True,
                context=self._context,
            )

    @callback
    def async_update_group_state(self) -> None:
        """Update the Lightener state based on the controlled entities."""

        # Independent changes to the brightness of the controlled entity
        # should not be set to this lightener.
        current_brightness = self._attr_brightness

        # Let the Group integration make its magic, which includes recalculating the brightness.
        super().async_update_group_state()

        # Reset the brightness back. See above comments.
        self._attr_brightness = current_brightness

        if self._attr_is_on is not True:
            return

        # Calculates the brighteness by checking if the current levels in al controlled lights
        # preciselly match one of the possible values for this lightener.
        levels = []
        for entity_id in self._entity_ids:
            state = self.hass.states.get(entity_id)

            # State may return None if the entity is not available, so we ignore it.
            if state is not None:
                for entity in self._entities:
                    if entity.entity_id == state.entity_id:
                        entity_brightness = state.attributes.get(ATTR_BRIGHTNESS) if state.state == STATE_ON else 0
                        if entity_brightness is not None:
                            levels.append(entity.translate_brightness_back(entity_brightness))
                        else:
                            levels.append([])

        common_level: set = set.intersection(*map(set, levels)) if levels else None

        if common_level:
            self._attr_brightness = common_level.pop()


class LightenerControlledLight:
    """Represents a light entity managed by a LightnerLight."""

    def __init__(
        self: LightenerControlledLight,
        entity_id: str,
        config: dict,
    ) -> None:
        self.entity_id = entity_id

        config_levels = {}

        for lightener_level, entity_value in config.get("brightness", {}).items():
            config_levels[
                _convert_percent_to_brightness(int(lightener_level))
            ] = _convert_percent_to_brightness(int(entity_value))

        config_levels.setdefault(255, 255)

        config_levels = OrderedDict(sorted(config_levels.items()))

        # Start the level list with value 0 for level 0.
        levels = [0]

        # List with all possible Lightener levels for a given entity level.
        to_lightener_levels = [[] for i in range(0,256)]

        previous_lightener_level = 0
        previous_light_level = 0

        # Fill all levels with the calculated values between the ranges.
        for lightener_level, light_level in config_levels.items():

            # Calculate all possible levels between the configured ranges
            # to be used during translation (lightener -> entity)
            for i in range(previous_lightener_level + 1, lightener_level):
                value_at_current_level = math.ceil(
                    previous_light_level
                    + (light_level - previous_light_level)
                    * (i - previous_lightener_level)
                    / (lightener_level - previous_lightener_level)
                )
                levels.append(value_at_current_level)
                to_lightener_levels[value_at_current_level].append(i)

            # To account for rounding, we use the configured values directly.
            levels.append(light_level)
            to_lightener_levels[light_level].append(lightener_level)

            # Do the reverse calculation for the oposite translation direction (entity -> lightener)
            for i in range(previous_light_level, light_level, 1 if previous_light_level < light_level else -1):
                value_at_current_level = math.ceil(
                    previous_lightener_level
                    + (lightener_level - previous_lightener_level)
                    * (i - previous_light_level)
                    / (light_level - previous_light_level)
                )

                # Since the same entity level can happen more than once (e.g. "50:100, 100:0") we
                # create a list with all possible lightener levels at this (i) entity brightness.
                if value_at_current_level not in to_lightener_levels[i]:
                    to_lightener_levels[i].append(value_at_current_level)

            previous_lightener_level = lightener_level
            previous_light_level = light_level

        self.levels = levels
        self.to_lightener_levels = to_lightener_levels

    def translate_brightness(self, brightness: int) -> int:
        """Calculates the entitiy brightness for the give Lightener brightness level."""

        return self.levels[brightness]

    def translate_brightness_back(self, brightness: int) -> list[int]:
        """Calculates all possible Lightener brightness levels for a give entity brightness."""

        if brightness is None:
            return []

        return self.to_lightener_levels[brightness]
