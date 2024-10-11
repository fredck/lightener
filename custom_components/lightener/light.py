"""Platform for Lightener lights."""

from __future__ import annotations

import logging
from types import MappingProxyType
from typing import Any

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.components.group.light import FORWARDED_ATTRIBUTES, LightGroup
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_TRANSITION,
    ColorMode,
)
from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_ENTITIES,
    CONF_FRIENDLY_NAME,
    CONF_LIGHTS,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_ON,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.config_validation import PLATFORM_SCHEMA
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util.color import value_to_brightness

from . import async_migrate_data, async_migrate_entry
from .const import DOMAIN, TYPE_ONOFF
from .util import get_light_type

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


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up entities for config entries."""
    unique_id = config_entry.entry_id

    await async_migrate_entry(hass, config_entry)

    # The unique id of the light will simply match the config entry ID.
    async_add_entities([LightenerLight(hass, config_entry.data, unique_id)])


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,  # pylint: disable=unused-argument
) -> None:
    """Set up entities for configuration.yaml entries."""

    lights = []

    for object_id, entity_config in config[CONF_LIGHTS].items():
        data = await async_migrate_data(entity_config, 1)
        data["entity_id"] = object_id

        lights.append(LightenerLight(hass, data))

    async_add_entities(lights)


class LightenerLight(LightGroup):
    """Represents a Lightener light."""

    _is_frozen = False
    _prefered_brightness = None

    def __init__(
        self,
        hass: HomeAssistant,
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
                    LightenerControlledLight(entity_id, entity_config, hass=hass)
                )

        super().__init__(
            unique_id=unique_id,
            name=config_data[CONF_FRIENDLY_NAME] if unique_id is None else None,
            entity_ids=entity_ids,
            mode=None,
        )

        self._attr_has_entity_name = unique_id is not None

        if self._attr_has_entity_name:
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, self.unique_id)},
                name=config_data[CONF_FRIENDLY_NAME],
            )

        self._entities = entities

        _LOGGER.debug(
            "Created lightener `%s`",
            config_data[CONF_FRIENDLY_NAME],
        )

    @property
    def color_mode(self) -> str:
        """Return the color mode of the light."""

        if not self.is_on:
            return None

        # If the controlled lights are on/off only, we force the color mode to BRIGHTNESS
        # since Lightner always support it.
        if self._attr_color_mode == ColorMode.ONOFF:
            return ColorMode.BRIGHTNESS

        # The group may calculate the color mode as UNKNOWN if any of the controlled lights is UNKNOWN.
        # We don't want that, so we force it to BRIGHTNESS.
        if self._attr_color_mode == ColorMode.UNKNOWN:
            return ColorMode.BRIGHTNESS

        return self._attr_color_mode

    @property
    def supported_color_modes(self) -> set[str] | None:
        """Flag supported color modes."""

        color_modes = super().supported_color_modes or set()

        # We support BRIGHNESS if the controlled lights are not on/off only.
        color_modes.discard(ColorMode.ONOFF)

        if len(color_modes) == 0:
            # As a minimum, we support the current color mode, or default to BRIGHTNESS.
            if (
                self.color_mode
                and self.color_mode != ColorMode.UNKNOWN
                and self.color_mode != ColorMode.ONOFF
            ):
                color_modes.add(self.color_mode)
            else:
                color_modes.add(ColorMode.BRIGHTNESS)

        return color_modes

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Forward the turn_on command to all controlled lights."""

        # This is basically a copy of LightGroup::async_turn_on but it has been changed
        # so we can pass different brightness to each light.

        # List all attributes we want to forward.
        data = {
            key: value for key, value in kwargs.items() if key in FORWARDED_ATTRIBUTES
        }

        # Retrieve the brightness being set to the Lightener
        brightness = kwargs.get(ATTR_BRIGHTNESS)

        # If the brightness is not being set, check if it was set in the Lightener.
        if brightness is None and self._attr_brightness:
            brightness = self._attr_brightness
        else:
            # Update the Lightener brightness level to the one being set.
            self._attr_brightness = brightness

        if brightness is None:
            brightness = self._prefered_brightness
        else:
            self._prefered_brightness = brightness

        _LOGGER.debug(
            "[Turn On] Attempting to set brightness of `%s` to `%s`",
            self.entity_id,
            brightness,
        )

        self._is_frozen = True

        for entity in self._entities:
            service = SERVICE_TURN_ON
            entity_brightness = None

            # If the brightness is being set in the lightener, translate it to the entity level.
            if brightness is not None:
                entity_brightness = entity.translate_brightness(brightness)

            # If the light brightness level is zero, we turn it off instead.
            if entity_brightness == 0:
                service = SERVICE_TURN_OFF
                entity_data = {}

                # "Transition" is the only additional data allowed with the turn_off service.
                if ATTR_TRANSITION in data:
                    entity_data[ATTR_TRANSITION] = data[ATTR_TRANSITION]
            else:
                # Make a copy of the data being sent to the lightener call so we can modify it.
                entity_data = data.copy()

                # Set the translated brightness level.
                if brightness is not None:
                    entity_data[ATTR_BRIGHTNESS] = entity_brightness

            # Set the proper entity ID.
            entity_data[ATTR_ENTITY_ID] = entity.entity_id

            await self.hass.services.async_call(
                LIGHT_DOMAIN,
                service,
                entity_data,
                blocking=True,
                context=self._context,
            )

            _LOGGER.debug(
                "Service `%s` called for `%s` (%s) with `%s`",
                service,
                entity.entity_id,
                entity.type,
                entity_data,
            )

        self._is_frozen = False

        # Define a coroutine as a ha task.
        async def _async_refresh() -> None:
            """Turn on all lights controlled by this Lightener."""
            self.async_update_group_state()
            self.async_write_ha_state()

        # Schedule the task to run.
        self.hass.async_create_task(
            _async_refresh(), name="Lightener [turn_on refresh]"
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off all lights controlled by this Lightener."""
        self._is_frozen = True

        self._prefered_brightness = self._attr_brightness

        await super().async_turn_off(**kwargs)

        _LOGGER.debug("[Turn Off] Turned off `%s`", self.entity_id)

        self._is_frozen = False
        self.async_update_group_state()
        self.async_write_ha_state()

    def turn_on(self, **kwargs: Any) -> None:
        """Turn the lights controlled by this Lightener on. There is no guarantee that this method is synchronous."""
        self.async_turn_on(**kwargs)

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the lights controlled by this Lightener off. There is no guarantee that this method is synchronous."""
        self.async_turn_off(**kwargs)

    @callback
    def async_update_group_state(self) -> None:
        """Update the Lightener state based on the controlled entities."""

        if self._is_frozen:
            return

        was_off = not self.is_on
        current_brightness = self._attr_brightness

        # Flag is this update is caused by this Lightener when calling turn_on.
        is_lightener_change = False

        # Let the Group integration make its magic, which includes recalculating the brightness.
        super().async_update_group_state()

        common_level: set = None

        if self.is_on:
            # Calculates the brighteness by checking if the current levels in al controlled lights
            # preciselly match one of the possible values for this lightener.
            levels = []
            for entity_id in self._entity_ids:
                state = self.hass.states.get(entity_id)

                # State may return None if the entity is not available, so we ignore it.
                if state is not None:
                    for entity in self._entities:
                        if entity.entity_id == state.entity_id:
                            # Check if the entity state change is caused by this Lightener.
                            is_lightener_change = (
                                True
                                if is_lightener_change
                                else (
                                    state.context
                                    and self._context
                                    and state.context.id == self._context.id
                                )
                            )

                            if state.state == STATE_ON:
                                entity_brightness = state.attributes.get(
                                    ATTR_BRIGHTNESS, 255
                                )
                            else:
                                entity_brightness = 0

                            _LOGGER.debug(
                                "Current brightness of `%s` is `%s`",
                                entity.entity_id,
                                entity_brightness,
                            )

                            if entity_brightness is not None:
                                levels.append(
                                    entity.translate_brightness_back(entity_brightness)
                                )
                            else:
                                levels.append([])

            if levels:
                # If the current lightener level is not present in the possible levels of the controlled lights.
                if len({self._prefered_brightness}.intersection(*map(set, levels))) > 0:
                    common_level = {self._prefered_brightness}
                else:
                    # Build a list of levels which are common for all lights.
                    common_level = set.intersection(*map(set, levels))

        if common_level:
            # Use the common level if any was found.
            self._attr_brightness = common_level.pop()
        else:
            self._attr_brightness = (
                self._prefered_brightness
                if is_lightener_change
                else current_brightness
                if self.is_on or was_off
                else None
            )

        _LOGGER.debug(
            "Setting the brightness of `%s` to `%s`",
            self.entity_id,
            self._attr_brightness,
        )

    @callback
    def async_write_ha_state(self) -> None:
        """Write the state to the state machine."""

        if self._is_frozen:
            return

        _LOGGER.debug(
            "Writing state of `%s` with brightness `%s`",
            self.entity_id,
            self._attr_brightness,
        )

        super().async_write_ha_state()


class LightenerControlledLight:
    """Represents a light entity managed by a LightnerLight."""

    def __init__(
        self: LightenerControlledLight,
        entity_id: str,
        config: dict,
        hass: HomeAssistant,
    ) -> None:
        """Create and instance of this class."""

        self.entity_id = entity_id
        self.hass = hass

        # Get the brightness configuration and prepare it for processing,
        brightness_config = prepare_brightness_config(config.get("brightness", {}))

        # Create the brightness conversion maps (from lightener to entity and from entity to lightener).
        self.levels = create_brightness_map(brightness_config)
        self.to_lightener_levels = create_reverse_brightness_map(
            brightness_config, self.levels
        )
        self.to_lightener_levels_on_off = create_reverse_brightness_map_on_off(
            self.to_lightener_levels
        )

    @property
    def type(self) -> str | None:
        """The entity type."""

        try:
            return get_light_type(self.hass, self.entity_id)
        except HomeAssistantError:
            return None

    def translate_brightness(self, brightness: int) -> int:
        """Calculate the entitiy brightness for the give Lightener brightness level."""

        level = self.levels.get(int(brightness))

        if self.type == TYPE_ONOFF:
            return 0 if level == 0 else 255

        return level

    def translate_brightness_back(self, brightness: int) -> list[int]:
        """Calculate all possible Lightener brightness levels for a give entity brightness."""

        if brightness is None:
            return []

        levels = self.to_lightener_levels.get(int(brightness))

        if self.type == TYPE_ONOFF:
            return self.to_lightener_levels_on_off[int(brightness)]

        return levels


def translate_config_to_brightness(config: dict) -> dict:
    """Create a copy of config converting the 0-100 range to 1-255.

    Convert the values to integers since the original values are strings.
    """

    return {
        value_to_brightness((1, 100), int(k)): 0
        if int(v) == 0
        else value_to_brightness((1, 100), int(v))
        for k, v in config.items()
    }


def prepare_brightness_config(config: dict) -> dict:
    """Convert the brightness configuration to a list of tuples and sorts it by the lightener level.

    Also add the default 0 and 255 levels if they are not present.
    """

    config = translate_config_to_brightness(config)

    # Zero must always be zero.
    config[0] = 0

    # If the maximum level is not present, add it.
    config.setdefault(255, 255)

    # Transform the dictionary into a list of tuples and sort it by the lightener level.
    config = sorted(config.items())

    return config


def create_brightness_map(config: list) -> dict:
    """Create a mapping of lightener levels to entity levels."""

    brightness_map = {0: 0}

    for i in range(1, len(config)):
        start, end = config[i - 1][0], config[i][0]
        start_value, end_value = config[i - 1][1], config[i][1]
        for j in range(start + 1, end + 1):
            brightness_map[j] = scale_ranged_value_to_int_range(
                (start, end), (start_value, end_value), j
            )

    return brightness_map


def create_reverse_brightness_map(config: list, lightener_levels: dict) -> dict:
    """Create a map with all entity level (from 0 to 255) to all possible lightener levels at each entity level.

    There can be multiple lightener levels for a single entity level.
    """

    # Initialize with all levels from 0 to 255.
    reverse_brightness_map = {i: [] for i in range(256)}

    # Initialize entries with all lightener levels (it goes from 0 to 255)
    for k, v in lightener_levels.items():
        reverse_brightness_map[v].append(k)

    # Now fill the gaps in the map by looping though the configured entity ranges
    for i in range(1, len(config)):
        start, end = config[i - 1][0], config[i][0]
        start_value, end_value = config[i - 1][1], config[i][1]

        # If there is an entity range to be covered
        if start_value != end_value:
            order = 1 if start_value < end_value else -1

            # Loop through the entity range
            for j in range(start_value, end_value + order, order):
                entity_level = scale_ranged_value_to_int_range(
                    (start_value, end_value), (start, end), j
                )
                # If the entry is not yet present for into that level, add it.
                if entity_level not in reverse_brightness_map[j]:
                    reverse_brightness_map[j].append(entity_level)

    return reverse_brightness_map


def create_reverse_brightness_map_on_off(reverse_map: dict) -> dict:
    """Create a reversed map dedicated to on/off lights."""

    # Build the "on" state out of all levels which are not in the "off" state.
    on_levels = [i for i in range(1, 256) if i not in reverse_map[0]]

    # The "on" levels are possible for all non-zero levels.
    reverse_map_on_off = {i: on_levels for i in range(1, 256)}

    # The "off" matches the normal reverse map.
    reverse_map_on_off[0] = reverse_map[0]

    return reverse_map_on_off


def scale_ranged_value_to_int_range(
    source_range: tuple[float, float],
    target_range: tuple[float, float],
    value: float,
) -> int:
    """Scale a value from one range to another and return an integer."""

    # Unpack the original and target ranges
    (a, b) = source_range
    (c, d) = target_range

    # Calculate the conversion
    y = c + ((value - a) * (d - c)) / (b - a)
    return round(y)
