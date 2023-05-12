"""Tests for __init__"""

import logging
from unittest.mock import Mock, patch

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from custom_components.lightener import async_migrate_entry
from custom_components.lightener.config_flow import LightenerConfigFlow
from custom_components.lightener.const import DOMAIN


async def test_migrate_entry_current(hass: HomeAssistant) -> None:
    """Test is the migration does nothing for an up-to-date configuration"""

    config_entry = ConfigEntry(
        LightenerConfigFlow.VERSION, "lightener", DOMAIN, {}, "user"
    )

    data = config_entry.data

    assert await async_migrate_entry(hass, config_entry) is True

    assert config_entry.data is data


async def test_migrate_entry_v1(hass: HomeAssistant) -> None:
    """Test is the migration does nothing for an up-to-date configuration"""

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

    config_entry = ConfigEntry(1, "lightener", DOMAIN, config_v1, "user")

    mock = Mock()

    with patch.object(hass.config_entries, "async_update_entry") as mock:
        assert await async_migrate_entry(hass, config_entry) is True

    assert mock.call_count == 1
    assert mock.call_args.kwargs.get("data") == {
        "friendly_name": "Test",
        "entities": {
            "light.test1": {"brightness": {"10": "20", "30": "40"}},
            "light.test2": {"brightness": {"50": "60", "70": "80"}},
        },
    }


async def test_migrate_entry_v1_no_update_hass(hass: HomeAssistant) -> None:
    """Test is the migration does nothing for an up-to-date configuration"""

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

    config_entry = ConfigEntry(1, "lightener", DOMAIN, config_v1, "user")

    mock = Mock()

    with patch.object(hass.config_entries, "async_update_entry") as mock:
        assert await async_migrate_entry(hass, config_entry, False) is True

    assert mock.call_count == 0

    assert config_entry.data == {
        "friendly_name": "Test",
        "entities": {
            "light.test1": {"brightness": {"10": "20", "30": "40"}},
            "light.test2": {"brightness": {"50": "60", "70": "80"}},
        },
    }


async def test_migrate_unkown_version(hass: HomeAssistant) -> None:
    """Test is the migration does nothing for an up-to-date configuration"""

    config_entry = ConfigEntry(1000, "lightener", DOMAIN, {}, "user")

    with patch.object(logging.Logger, "error") as mock:
        assert await async_migrate_entry(hass, config_entry, False) is False

    mock.assert_called_once_with('Unknow configuration version "%i"', 1000)
