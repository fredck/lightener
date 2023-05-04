"""Lightener Integration."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, CONF_PORT, Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN

PLATFORMS = [Platform.LIGHT]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Setup platform from a config entry."""

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, Platform.LIGHT)
    )

    return True


async def async_remove_config_entry_device() -> bool:
    """Remove a config entry from a device."""

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    # Forward the unloading of the entry to the platform.
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    return unload_ok
