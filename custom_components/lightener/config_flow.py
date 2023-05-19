"""The config flow for Lightener."""

import re
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_ENTITIES, CONF_FRIENDLY_NAME, CONF_BRIGHTNESS
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowHandler, FlowResult
from homeassistant.helpers.entity_registry import (
    async_entries_for_config_entry,
    async_get,
)
from homeassistant.helpers.selector import selector

from .const import DOMAIN


class LightenerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Lightener config flow."""

    # The schema version of the entries that it creates.
    # Home Assistant will call the migrate method if the version changes.
    VERSION = 2

    def __init__(self) -> None:
        """Initialize options flow."""
        self.lightener_flow = LightenerFlow(self, steps={"name": "user"})
        super().__init__()

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        """Configure the lighener device name"""

        return await self.lightener_flow.async_step_name(user_input)

    async def async_step_lights(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manages the selection of the lights controlled by the Lighetner light."""
        return await self.lightener_flow.async_step_lights(user_input)

    async def async_step_light_configuration(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manages the configuration for each controlled light."""
        return await self.lightener_flow.async_step_light_configuration(user_input)

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""

        return LightenerOptionsFlow(config_entry)


class LightenerOptionsFlow(config_entries.OptionsFlow):
    """The options flow handler for Lightener."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.lightener_flow = LightenerFlow(
            self, steps={"lights": "init"}, config_entry=config_entry
        )
        super().__init__()

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manages the selection of the lights controlled by the Lighetner light."""
        return await self.lightener_flow.async_step_lights(user_input)

    async def async_step_light_configuration(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manages the configuration for each controlled light."""
        return await self.lightener_flow.async_step_light_configuration(user_input)


class LightenerFlow:
    """Holds steps for both the config and the options flow"""

    def __init__(
        self,
        flow_handler: FlowHandler,
        steps: dict,
        config_entry: config_entries.ConfigEntry | None = None,
    ) -> None:
        self.flow_handler = flow_handler
        self.config_entry = config_entry
        self.data = {} if config_entry is None else config_entry.data.copy()
        self.local_data = {}
        self.steps = steps

    async def async_step_name(self, user_input: dict[str, Any] | None = None):
        """Configure the lighener device name"""

        errors = {}

        if user_input is not None:
            name = user_input["name"]

            self.data[CONF_FRIENDLY_NAME] = name

            return await self.async_step_lights()

        data_schema = {
            vol.Required("name"): str,
        }

        return self.flow_handler.async_show_form(
            step_id=self.steps.get("name", "name"),
            last_step=False,
            data_schema=vol.Schema(data_schema),
            errors=errors,
        )

    async def async_step_lights(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manages the selection of the lights controlled by the Lighetner light."""

        errors = {}

        lightener_entities = []
        controlled_entities = []

        if self.config_entry is not None:
            # Create a list with the ids of the Lightener entities we're configuring.
            # Most likely we'll have a single item in the list.
            entity_registry = async_get(self.flow_handler.hass)
            lightener_entities = async_entries_for_config_entry(
                entity_registry, self.config_entry.entry_id
            )
            lightener_entities = list(map(lambda e: e.entity_id, lightener_entities))

            # Load the previously configured list of entities controlled by this Lightener.
            controlled_entities = list(
                self.config_entry.data.get(CONF_ENTITIES, {}).keys()
            )

        if user_input is not None:
            controlled_entities = self.local_data[
                "controlled_entities"
            ] = user_input.get("controlled_entities")

            if not controlled_entities:
                errors["controlled_entities"] = "controlled_entities_empty"
            else:
                entities = self.data[CONF_ENTITIES] = {}

                for entity in controlled_entities:
                    entities[entity] = {}

                return await self.async_step_light_configuration()

        return self.flow_handler.async_show_form(
            step_id=self.steps.get("lights", "lights"),
            last_step=False,
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "controlled_entities", default=controlled_entities
                    ): selector(
                        {
                            "entity": {
                                "multiple": True,
                                "filter": {"domain": "light"},
                                "exclude_entities": lightener_entities,
                            }
                        }
                    )
                }
            ),
            errors=errors,
        )

    async def async_step_light_configuration(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manages the configuration for each controlled light."""

        brightness = ""
        placeholders = {}
        errors = {}

        controlled_entities = self.local_data.get("controlled_entities")

        if user_input is not None:
            brightness = {}

            for entry in user_input.get("brightness", "").splitlines():
                match = re.fullmatch(r"^\s*(\d+)\s*:\s*(\d+)\s*$", entry)

                if match is not None:
                    left = int(match.group(1))
                    right = int(match.group(2))

                    if left >= 1 and left <= 100 and right <= 100:
                        brightness[str(left)] = str(right)
                        continue

                errors["brightness"] = "invalid_brightness"
                placeholders["error_entry"] = entry
                break

            if len(errors) == 0:
                entities: dict = self.data.get(CONF_ENTITIES)
                entities.get(self.local_data.get("current_light"))[
                    CONF_BRIGHTNESS
                ] = brightness

                if len(controlled_entities):
                    return await self.async_step_light_configuration()

                return await self.async_save_data()
        else:
            light = self.local_data["current_light"] = controlled_entities.pop(0)

        light = self.local_data["current_light"]
        state = self.flow_handler.hass.states.get(light)
        placeholders["light_name"] = state.name

        if user_input is None:
            # Load the previously configured data.
            if self.config_entry is not None:
                brightness = (
                    self.config_entry.data.get(CONF_ENTITIES, {})
                    .get(light, {})
                    .get(CONF_BRIGHTNESS, {})
                )

                brightness = "\n".join(
                    [(str(key) + ": " + str(brightness[key])) for key in brightness]
                )
        else:
            brightness = user_input["brightness"]

        schema = {
            vol.Optional(
                "brightness", description={"suggested_value": brightness}
            ): selector({"template": {}})
        }

        return self.flow_handler.async_show_form(
            step_id=self.steps.get("light_configuration", "light_configuration"),
            last_step=len(controlled_entities) == 0,
            data_schema=vol.Schema(schema),
            description_placeholders=placeholders,
            errors=errors,
        )

    async def async_save_data(self) -> FlowResult:
        """Saves the configured data."""

        # We don't save it into the "options" key but always in "config",
        # no matter if the user called the config or the options flow.

        # If in a config flow, create the config entry.
        if self.config_entry is None:
            return self.flow_handler.async_create_entry(
                title=self.data.get(CONF_FRIENDLY_NAME), data=self.data
            )

        # In an options flow, update the config entry.
        self.flow_handler.hass.config_entries.async_update_entry(
            self.config_entry, data=self.data, options=self.config_entry.options
        )

        await self.flow_handler.hass.config_entries.async_reload(
            self.config_entry.entry_id
        )

        return self.flow_handler.async_create_entry(title="", data={})
