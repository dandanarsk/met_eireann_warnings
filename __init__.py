"""Met Éireann Weather Warnings integration."""
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
    # Get polling interval from config entry, default to 30 minutes
    polling_interval = entry.data.get("polling_interval", 30)
    
    coordinator = MetEireannDataUpdateCoordinator(hass, polling_interval)
    
    # Set area configuration
    coordinator.area_config = {
        "area_type": entry.data.get("area_type", "whole_ireland"),
        "selected_regions": entry.data.get("selected_regions", []),
        "selected_counties": entry.data.get("selected_counties", [])
    }
    
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

    def __init__(self, hass: HomeAssistant, polling_interval: int = 30) -> None:
        """Initialize."""
        self.hass = hass
        self.area_config = {}  # Will be set by async_setup_entry
        # Convert minutes to timedelta
        update_interval = timedelta(minutes=polling_interval)
        
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=update_interval,
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

        # Handle case where data is None or empty
        if not data:
            return processed_data

        # The API returns a direct array of warnings, not a GeoJSON-like structure
        warnings_list = data if isinstance(data, list) else []

        for warning_data in warnings_list:
            warning = {
                "id": warning_data.get("id"),
                "cap_id": warning_data.get("capId"),
                "type": warning_data.get("type"),
                "level": warning_data.get("level"),
                "issued": warning_data.get("issued"),
                "updated": warning_data.get("updated"),
                "onset": warning_data.get("onset"),
                "expires": warning_data.get("expiry"),  # Note: API uses "expiry" not "expires"
                "headline": warning_data.get("headline"),
                "description": warning_data.get("description"),
                "instruction": warning_data.get("instruction"),
                "regions": warning_data.get("regions", []),
                "severity": warning_data.get("severity"),
                "certainty": warning_data.get("certainty"),
                "urgency": warning_data.get("urgency"),
                "status": warning_data.get("status", "").lower()
            }
            
            # Filter warnings based on area configuration
            if self._should_include_warning(warning):
                processed_data["warnings"].append(warning)
                
                # Track active warnings - check for "warning" status (Met Éireann uses this)
                if warning["status"] in ["warning", "actual", "active"]:
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

    def _should_include_warning(self, warning: dict) -> bool:
        """Check if warning should be included based on area configuration."""
        area_config = getattr(self, 'area_config', {})
        area_type = area_config.get("area_type", "whole_ireland")
        
        if area_type == "whole_ireland":
            return True
            
        warning_region_codes = warning.get("regions", [])
        
        # Convert region codes to county names
        from .const import REGION_CODES
        warning_counties = []
        for code in warning_region_codes:
            county = REGION_CODES.get(code)
            if county:
                warning_counties.append(county)
        
        if area_type == "regions":
            selected_regions = area_config.get("selected_regions", [])
            
            # Check if any of the warning counties belong to selected regions
            from .const import REGION_TO_COUNTIES
            for selected_region in selected_regions:
                region_counties = REGION_TO_COUNTIES.get(selected_region, [])
                for warning_county in warning_counties:
                    if warning_county in region_counties:
                        return True
            return False
            
        elif area_type == "counties":
            selected_counties = area_config.get("selected_counties", [])
            
            # Check if any warning counties match selected counties
            for warning_county in warning_counties:
                if warning_county in selected_counties:
                    return True
            return False
            
        return True
