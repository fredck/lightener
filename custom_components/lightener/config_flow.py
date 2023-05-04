"""The config flow for Lightener."""

from typing import Any

import voluptuous as vol

from homeassistant import config_entries

from homeassistant.const import (
    CONF_FRIENDLY_NAME,
)

from .const import DOMAIN


class LightenerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Lightener config flow."""

    # The schema version of the entries that it creates.
    # Home Assistant will call the migrate method if the version changes.
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        """Configure the lighener device name"""

        errors = {}

        if user_input is not None:
            name = user_input["name"]

            data = {}
            data[CONF_FRIENDLY_NAME] = name

            return self.async_create_entry(title=name, data=data)

        data_schema = {
            vol.Required("name"): str,
        }

        return self.async_show_form(
            step_id="user", data_schema=vol.Schema(data_schema), errors=errors
        )
