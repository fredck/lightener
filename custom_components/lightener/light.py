"""Platform for Lightener lights."""

from __future__ import annotations

import logging
from types import MappingProxyType
from typing import Any, Literal
from collections import OrderedDict

import math

import homeassistant.helpers.config_validation as cv
import homeassistant.util.ulid as ulid_util
import voluptuous as vol
from homeassistant import core
from homeassistant.components.light import ATTR_BRIGHTNESS
from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.components.light import ENTITY_ID_FORMAT, ColorMode, LightEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_ENTITIES,
    CONF_FRIENDLY_NAME,
    CONF_LIGHTS,
    EVENT_HOMEASSISTANT_STARTED,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import Context, HomeAssistant, State
from homeassistant.helpers.config_validation import PLATFORM_SCHEMA
from homeassistant.helpers.entity import DeviceInfo, async_generate_entity_id
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import Event, async_track_state_change_event
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import async_migrate_entry
from .const import DOMAIN

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
    async_add_entities([LightenerLight(hass, config_entry.data, unique_id)])


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

        entry.data["entity_id"] = object_id
        lights.append(LightenerLight(hass, entry.data))

    async_add_entities(lights)


class LightenerLight(LightEntity):
    """Represents a Lightener light."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_data: MappingProxyType,
        unique_id: str | None = None,
    ) -> None:
        """Initialize the light using the config entry information."""

        self.hass = hass

        # Configuration coming from configuration.yaml will have no unique id.
        self._unique_id = unique_id

        # Setup the id for this light. E.g. "light.living_room" if the name is "Living room".
        self.entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT,
            config_data.get("entity_id", config_data[CONF_FRIENDLY_NAME]),
            hass=hass,
        )

        # Define the display name of the light.
        self._name = config_data[CONF_FRIENDLY_NAME]

        self._state = STATE_OFF
        self._brightness = 255

        ## Add all entities that are managed by this lightened.

        entities = []

        if config_data.get(CONF_ENTITIES) is not None:
            for entity_id, entity_config in config_data[CONF_ENTITIES].items():
                entities.append(
                    LightenerLightEntity(hass, self, entity_id, entity_config)
                )

        self._entities = entities

    @property
    def should_poll(self) -> bool:
        return False

    @property
    def unique_id(self) -> str | None:
        return self._unique_id

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return the device info."""

        if self.unique_id is None:
            return None

        return DeviceInfo(identifiers={(DOMAIN, self.unique_id)}, name=self._name)

    @property
    def name(self) -> str:
        """Return the display name of this light."""

        # This entity is the main feature (light) of the device, so we must return None.
        if self.unique_id is not None:
            return None

        return self._name

    @property
    def has_entity_name(self) -> bool:
        return True

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

            # The event may be fired with empty state when renaming the entity ID. In such case we do nothing.
            if new_state is not None:
                # Update the local state with the event one.
                self._state = new_state.state
                self._brightness = (
                    new_state.attributes.get(ATTR_BRIGHTNESS) or self._brightness
                )

                if new_state.state == STATE_ON:
                    for entity in self._entities:
                        await entity.async_turn_on(self._brightness)

                else:
                    for entity in self._entities:
                        await entity.async_turn_off()

        self.async_on_remove(
            async_track_state_change_event(
                self.hass, self.entity_id, _async_state_change
            )
        )

        # Track state changes of the child entities and update the lightener state accordingly.

        async def _async_child_state_change(ev: Event) -> None:
            # Do nothing if the change has been triggered by the lightener.
            if ev.context.id == LIGHTENER_CONTEXT:
                return

            service_to_call = SERVICE_TURN_OFF

            if any(entity.state == STATE_ON for entity in self._entities):
                service_to_call = SERVICE_TURN_ON

            self.hass.async_create_task(
                self.hass.services.async_call(
                    core.DOMAIN,
                    service_to_call,
                    {ATTR_ENTITY_ID: self.entity_id},
                    blocking=True,
                    context=Context(None, None, LIGHTENER_CONTEXT),
                )
            )

        self.async_on_remove(
            async_track_state_change_event(
                self.hass,
                map(lambda e: e.entity_id, self._entities),
                _async_child_state_change,
            )
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
        self.hass = hass
        self._parent = parent

        config_levels = {}

        for lightener_level, entity_value in config.get("brightness", {}).items():
            config_levels[
                _convert_percent_to_brightness(int(lightener_level))
            ] = _convert_percent_to_brightness(int(entity_value))

        config_levels.setdefault(255, 255)

        config_levels = OrderedDict(sorted(config_levels.items()))

        # Start the level list with value 0 for level 0.
        levels = [0]

        previous_lightener_level = 0
        previous_light_level = 0

        # Fill all levels with the calculated values between the ranges.
        for lightener_level, light_level in config_levels.items():
            for i in range(previous_lightener_level + 1, lightener_level):
                value_at_current_level = math.ceil(
                    previous_light_level
                    + (light_level - previous_light_level)
                    * (i - previous_lightener_level)
                    / (lightener_level - previous_lightener_level)
                )
                levels.append(value_at_current_level)

            # To account for rounding, we use the configured values directly.
            levels.append(light_level)

            previous_lightener_level = lightener_level
            previous_light_level = light_level

        self._levels = levels

        # Track the entity availability.
        self._is_available = hass.states.get(self._entity_id) is not None

        async def _async_state_changed(event: Event) -> None:
            self._is_available = event.data.get("new_state") is not None

        parent.async_on_remove(
            async_track_state_change_event(hass, entity_id, _async_state_changed)
        )

        async def _async_check_available(event: Event) -> None:
            if not self._is_available:
                _LOGGER.warning(
                    "Unable to find referenced entity %s or it is currently not available",
                    entity_id,
                )

        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, _async_check_available)

    @property
    def entity_id(self: LightenerLightEntity) -> str:
        """The original entity id of this managed entity."""

        return self._entity_id

    @property
    def state(self: LightenerLightEntity) -> Literal["on", "off"] | None:
        """The current state of this entity."""

        if not self._is_available:
            return None

        return self.hass.states.get(self._entity_id).state

    async def async_turn_on(self: LightenerLightEntity, brightness: int) -> None:
        """Turns the light on or off, according to the lightened configuration for the given brighteness."""

        if not self._is_available:
            return

        self.hass.async_create_task(
            self.hass.services.async_call(
                LIGHT_DOMAIN,
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

        if not self._is_available:
            return

        self.hass.async_create_task(
            self.hass.services.async_call(
                LIGHT_DOMAIN,
                SERVICE_TURN_OFF,
                {ATTR_ENTITY_ID: self._entity_id},
                blocking=True,
                context=Context(None, None, LIGHTENER_CONTEXT),
            )
        )
