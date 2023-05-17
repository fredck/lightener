"""Fixtures for testing."""

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield

@pytest.fixture(autouse=True)
async def setup_components(hass: HomeAssistant):
    """Register test lights used in tests"""

    await async_setup_component(hass,"homeassistant", {})
    await async_setup_component(hass,"light", {})

@pytest.fixture(autouse=True)
def register_test_lights(hass: HomeAssistant):
    """Register test lights used in tests"""

    hass.states.async_set(entity_id="light.test1", new_state="off")
    hass.states.async_set(entity_id="light.test2", new_state="off")
