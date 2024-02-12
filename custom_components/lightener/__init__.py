"""Lightener Integration."""

import logging
from types import MappingProxyType

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .config_flow import LightenerConfigFlow

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.LIGHT]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up platform from a config entry."""

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    # Forward the unloading of the entry to the platform.
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    return unload_ok


async def async_migrate_entry(
    hass: HomeAssistant, config_entry: ConfigEntry, update_hass: bool = True
) -> bool:
    """Update old versions of the configuration to the current format."""

    version = config_entry.version
    data = config_entry.data

    # Lightener 1.x didn't have config entries, just manual configuration.yaml. We consider this the no-version option.
    if config_entry.version is None or config_entry.version == 1:
        new_data = {
            "entities": {},
        }

        if data.get("friendly_name") is not None:
            new_data["friendly_name"] = data["friendly_name"]

        for entity, brightness in data.get("entities", {}).items():
            new_data.get("entities")[entity] = {"brightness": brightness}

        config_entry.version = 2

        if update_hass is True:
            hass.config_entries.async_update_entry(config_entry, data=new_data)
        else:
            config_entry.data = MappingProxyType(new_data)

        return True

    if config_entry.version == LightenerConfigFlow.VERSION:
        return True

    _LOGGER.error('Unknow configuration version "%i"', version)
    return False


async def async_remove_config_entry_device() -> bool:
    """Remove a config entry from a device."""

    return True
