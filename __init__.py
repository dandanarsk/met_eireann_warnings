from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Any

import aiohttp
import async_timeout
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

_LOGGER = logging.getLogger(__name__)

DOMAIN = "met_eireann_warnings"
PLATFORMS = [Platform.SENSOR]

API_URL = "https://www.met.ie/Open_Data/json/warning_IRELAND.json"
UPDATE_INTERVAL = timedelta(minutes=10)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Met Éireann Weather Warnings from a config entry."""
    coordinator = MetEireannDataUpdateCoordinator(hass)
    
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class MetEireannDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Met Éireann weather warnings data."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize."""
        self.hass = hass
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Update data via Met Éireann API."""
        session = async_get_clientsession(self.hass)
        
        try:
            async with async_timeout.timeout(30):
                async with session.get(API_URL) as response:
                    if response.status != 200:
                        raise UpdateFailed(f"Error communicating with API: {response.status}")
                    
                    data = await response.json()
                    return self._process_warnings_data(data)
                    
        except asyncio.TimeoutError as err:
            raise UpdateFailed("Timeout communicating with Met Éireann API") from err
        except aiohttp.ClientError as err:
            raise UpdateFailed(f"Error communicating with Met Éireann API: {err}") from err

    def _process_warnings_data(self, data: dict) -> dict[str, Any]:
        """Process the raw API data into a structured format."""
        processed_data = {
            "warnings": [],
            "active_warnings_count": 0,
            "highest_warning_level": None,
            "warning_types": set(),
            "regions_affected": set()
        }

        if not data or "features" not in data:
            return processed_data

        for feature in data["features"]:
            properties = feature.get("properties", {})
            
            warning = {
                "id": properties.get("id"),
                "type": properties.get("type"),
                "level": properties.get("level"),
                "onset": properties.get("onset"),
                "expires": properties.get("expires"),
                "headline": properties.get("headline"),
                "description": properties.get("description"),
                "instruction": properties.get("instruction"),
                "regions": properties.get("regions", []),
                "severity": properties.get("severity"),
                "certainty": properties.get("certainty"),
                "urgency": properties.get("urgency"),
                "status": properties.get("status", "").lower()
            }
            
            processed_data["warnings"].append(warning)
            
            # Track active warnings
            if warning["status"] in ["actual", "active"]:
                processed_data["active_warnings_count"] += 1
                
                # Track warning types and regions
                if warning["type"]:
                    processed_data["warning_types"].add(warning["type"])
                if warning["regions"]:
                    processed_data["regions_affected"].update(warning["regions"])
                
                # Track highest warning level
                level = warning.get("level", "").lower()
                if level in ["red", "orange", "yellow"]:
                    if processed_data["highest_warning_level"] is None:
                        processed_data["highest_warning_level"] = level
                    elif level == "red":
                        processed_data["highest_warning_level"] = "red"
                    elif level == "orange" and processed_data["highest_warning_level"] != "red":
                        processed_data["highest_warning_level"] = "orange"

        # Convert sets to lists for JSON serialization
        processed_data["warning_types"] = list(processed_data["warning_types"])
        processed_data["regions_affected"] = list(processed_data["regions_affected"])
        
        return processed_data