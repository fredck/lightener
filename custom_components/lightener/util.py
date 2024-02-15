"""Utility functions."""

from homeassistant.components.light import (
    brightness_supported,
    get_supported_color_modes,
)
from homeassistant.core import HomeAssistant

from .const import TYPE_DIMMABLE, TYPE_ONOFF


def get_light_type(hass: HomeAssistant, entity_id: str) -> str | None:
    """Return the type of light (TYPE_DIMMABLE or TYPE_ONOFF)."""

    supported_color_modes = get_supported_color_modes(hass, entity_id)

    return (
        (TYPE_DIMMABLE if brightness_supported(supported_color_modes) else TYPE_ONOFF)
        if supported_color_modes
        else None
    )
