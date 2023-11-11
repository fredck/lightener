"""Fixtures for testing."""

from collections.abc import Callable
from uuid import uuid4

import pytest
from homeassistant.components.light import ColorMode
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import async_get_platforms
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.lightener.light import LightenerLight


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integrations for all tests."""
    yield


@pytest.fixture(autouse=True)
async def setup_test_lights(hass: HomeAssistant):
    """Register test lights used in tests"""

    hass.states.async_set(
        entity_id="light.test1",
        new_state="off",
        attributes={"supported_color_modes": [ColorMode.BRIGHTNESS]},
    )
    hass.states.async_set(
        entity_id="light.test2",
        new_state="off",
        attributes={"supported_color_modes": [ColorMode.BRIGHTNESS]},
    )
    hass.states.async_set(
        entity_id="light.test_onoff",
        new_state="off",
        attributes={"supported_color_modes": [ColorMode.ONOFF]},
    )


@pytest.fixture
async def create_lightener(
    hass: HomeAssistant,
) -> Callable[[str, dict], LightenerLight]:
    """Creates a function used to create Lightners"""

    async def creator(name: str | None = None, config: dict | None = None) -> str:
        entry = MockConfigEntry(
            domain="lightener",
            unique_id=str(uuid4()),
            data={
                "friendly_name": name or "Test",
                "entities": {"light.test1": {}},
            }
            if config is None
            else config,
        )
        entry.add_to_hass(hass)

        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        platform = async_get_platforms(hass, "lightener")
        return platform[0].entities["light.test"]

    return creator
