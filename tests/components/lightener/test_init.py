"""Tests for __init__."""

import logging
from unittest.mock import patch

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity_registry import (
    async_get as async_get_entity_registry,
)
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.lightener import (
    async_migrate_entry,
    async_unload_entry,
)
from custom_components.lightener.config_flow import LightenerConfigFlow
from custom_components.lightener.const import DOMAIN


async def test_async_setup_entry(hass):
    """Test setting up Lightener successfully."""
    config_entry = MockConfigEntry(
        domain="lightener",
        data={
            "friendly_name": "Test",
            "entities": {
                "light.test1": {},
            },
        },
    )
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert "lightener.light" in hass.config.components


@patch("custom_components.lightener.async_unload_entry", wraps=async_unload_entry)
async def test_async_unload_entry(mock_unload, hass):
    """Test setting up Lightener successfully."""
    config_entry = MockConfigEntry(
        domain="lightener",
        data={
            "friendly_name": "Test",
            "entities": {
                "light.test1": {},
            },
        },
    )
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED
    assert "light.test" in hass.states.async_entity_ids()

    assert await hass.config_entries.async_remove(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.NOT_LOADED
    assert "light.test" not in hass.states.async_entity_ids()

    # Ensure that the Lightener unload implementation was called.
    mock_unload.assert_called_once()
    assert mock_unload.return_value


async def test_migrate_entry_current(hass: HomeAssistant) -> None:
    """Test is the migration does nothing for an up-to-date configuration."""

    config_entry = ConfigEntry(
        version=LightenerConfigFlow.VERSION,
        minor_version=LightenerConfigFlow.VERSION,
        title="lightener",
        domain=DOMAIN,
        data={},
        source="user",
        unique_id=None,
        options=None,
        discovery_keys=[],
        subentries_data={},
    )

    data = config_entry.data

    assert await async_migrate_entry(hass, config_entry) is True

    assert config_entry.data is data


async def test_migrate_entry_v1(hass: HomeAssistant) -> None:
    """Test is the migration does nothing for an up-to-date configuration."""

    config_v1 = {
        "friendly_name": "Test",
        "entities": {
            "light.test1": {
                "10": "20",
                "30": "40",
            },
            "light.test2": {
                "50": "60",
                "70": "80",
            },
        },
    }

    config_entry = ConfigEntry(
        version=1,
        minor_version=1,
        title="lightener",
        domain=DOMAIN,
        data=config_v1,
        source="user",
        unique_id=None,
        options=None,
        discovery_keys=[],
        subentries_data={},
    )

    with patch.object(hass.config_entries, "async_update_entry") as update_mock:
        assert await async_migrate_entry(hass, config_entry) is True

    assert update_mock.call_count == 1
    assert update_mock.call_args.kwargs.get("data") == {
        "friendly_name": "Test",
        "entities": {
            "light.test1": {"brightness": {"10": "20", "30": "40"}},
            "light.test2": {"brightness": {"50": "60", "70": "80"}},
        },
    }


async def test_migrate_unkown_version(hass: HomeAssistant) -> None:
    """Test is the migration does nothing for an up-to-date configuration."""

    config_entry = ConfigEntry(
        version=1000,
        minor_version=1000,
        title="lightener",
        domain=DOMAIN,
        data={},
        source="user",
        unique_id=None,
        options=None,
        discovery_keys=[],
        subentries_data={},
    )

    with patch.object(logging.Logger, "error") as mock:
        assert await async_migrate_entry(hass, config_entry) is False

    mock.assert_called_once_with('Unknow configuration version "%i"', 1000)


async def test_remove_device(
    hass: HomeAssistant, hass_ws_client, create_lightener
) -> None:
    """Ensure HA can remove the Lightener device."""

    # Create a Lightener via the helper so a device and entity are registered.
    lightener = await create_lightener()

    # Find the created entity and its device id.
    er = async_get_entity_registry(hass)
    entity_entry = er.async_get(lightener.entity_id)
    assert entity_entry is not None
    assert entity_entry.device_id is not None
    device_id = entity_entry.device_id
    assert entity_entry.config_entry_id is not None
    config_entry_id = entity_entry.config_entry_id

    # Ensure the config component is set up so it registers the device_registry websocket commands.
    assert await async_setup_component(hass, "config", {})
    await hass.async_block_till_done()

    # Call the websocket API to remove the config entry from the device.
    ws = await hass_ws_client(hass)
    ws_result = await ws.remove_device(device_id, config_entry_id)

    # It should succeed and return a result payload.
    assert ws_result["type"] == "result"
    assert ws_result["success"] is True

    # And the device should no longer reference this config entry.
    dev_reg = dr.async_get(hass)
    device_entry = dev_reg.async_get(device_id)
    if device_entry is not None:
        assert config_entry_id not in device_entry.config_entries
