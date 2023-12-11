"""Fixtures for testing."""

from collections.abc import Callable
from uuid import uuid4

import pytest
from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import async_get_platforms
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.lightener.light import LightenerLight


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integrations for all tests."""
    yield


@pytest.fixture(autouse=True)
async def setup_test_lights(hass: HomeAssistant):
    """Register test lights used in tests"""

    template_lights = {
        test: {
            "unique_id": test,
            "friendly_name": test,
            "turn_on": None,
            "turn_off": None,
            "set_level": None,
        }
        for test in ["test1", "test2", "test_onoff"]
    }

    # Make test_onoff support on/off only
    del template_lights["test_onoff"]["set_level"]

    await async_setup_component(
        hass,
        LIGHT_DOMAIN,
        {LIGHT_DOMAIN: [{"platform": "template", "lights": template_lights}]},
    )
    await hass.async_block_till_done()


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
