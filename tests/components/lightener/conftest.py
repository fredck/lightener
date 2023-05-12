"""Fixtures for testing."""

import pytest


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


@pytest.fixture(autouse=True)
def register_test_lights(hass):
    """Register test lights used in tests"""

    hass.states.async_set(entity_id="light.test1", new_state="off")
    hass.states.async_set(entity_id="light.test2", new_state="off")
