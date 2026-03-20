"""Met Éireann Weather Warnings integration with RSS fallback."""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Any
import xml.etree.ElementTree as ET

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
RSS_URL = "https://www.met.ie/warningsxml/rss.xml"
UPDATE_INTERVAL = timedelta(minutes=10)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Met Éireann Weather Warnings from a config entry."""
    polling_interval = entry.data.get("polling_interval", 30)
    
    coordinator = MetEireannDataUpdateCoordinator(hass, polling_interval)
    
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
        self.area_config = {}
        self._use_rss = False  # Track if using RSS fallback
        update_interval = timedelta(minutes=polling_interval)
        
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=update_interval,
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Update data via Met Éireann API with RSS fallback."""
        session = async_get_clientsession(self.hass)
        
        # Try JSON API first
        try:
            async with async_timeout.timeout(30):
                async with session.get(API_URL) as response:
                    if response.status == 200:
                        data = await response.json()
                        if self._use_rss:
                            _LOGGER.info("JSON API recovered, switching back from RSS")
                            self._use_rss = False
                        return self._process_warnings_data(data)
                    else:
                        _LOGGER.warning(f"JSON API returned {response.status}, trying RSS")
                        
        except (asyncio.TimeoutError, aiohttp.ClientError) as err:
            _LOGGER.warning(f"JSON API failed: {err}, trying RSS fallback")
        
        # Fallback to RSS feed
        try:
            async with async_timeout.timeout(30):
                async with session.get(RSS_URL) as response:
                    if response.status != 200:
                        raise UpdateFailed(f"Both APIs failed. RSS status: {response.status}")
                    
                    rss_data = await response.text()
                    if not self._use_rss:
                        _LOGGER.warning("JSON unavailable, using RSS feed")
                        self._use_rss = True
                    
                    return await self._process_rss_data(rss_data, session)
                    
        except asyncio.TimeoutError as err:
            raise UpdateFailed("Timeout on both JSON and RSS APIs") from err
        except aiohttp.ClientError as err:
            raise UpdateFailed(f"Error on both APIs: {err}") from err

    async def _process_rss_data(self, rss_data: str, session: aiohttp.ClientSession) -> dict[str, Any]:
        """Process RSS feed into same format as JSON."""
        try:
            root = ET.fromstring(rss_data)
            warnings_list = []
            warning_id = 1
            
            for item in root.findall('.//item'):
                title = item.find('title')
                link = item.find('link')
                description = item.find('description')
                
                if title is None or link is None:
                    continue
                
                # Parse title: "Yellow Wind Warning"
                title_text = title.text.strip()
                parts = title_text.split(' ')
                
                level = parts[0] if len(parts) > 0 else "Unknown"
                
                # Fetch CAP XML for details
                cap_url = link.text.strip()
                cap_data = await self._fetch_cap_data(cap_url, session)
                
                if cap_data:
                    warning = {
                        "id": warning_id,
                        "cap_id": cap_data.get("identifier", ""),
                        "type": f"{level.lower()}; {cap_data.get('severity', 'Moderate')}",
                        "level": level,
                        "issued": cap_data.get("sent", ""),
                        "updated": cap_data.get("sent", ""),
                        "onset": cap_data.get("onset", ""),
                        "expires": cap_data.get("expires", ""),
                        "headline": cap_data.get("headline", title_text),
                        "description": cap_data.get("description", description.text if description is not None else ""),
                        "regions": cap_data.get("regions", []),
                        "severity": cap_data.get("severity", "Moderate"),
                        "certainty": cap_data.get("certainty", "Likely"),
                        "urgency": cap_data.get("urgency", None),
                        "status": "warning"
                    }
                    warnings_list.append(warning)
                    warning_id += 1
            
            return self._process_warnings_data(warnings_list)
            
        except ET.ParseError as err:
            _LOGGER.error(f"Error parsing RSS XML: {err}")
            raise UpdateFailed(f"RSS parse error: {err}") from err

    async def _fetch_cap_data(self, cap_url: str, session: aiohttp.ClientSession) -> dict[str, Any]:
        """Fetch CAP XML for detailed warning info."""
        try:
            async with async_timeout.timeout(10):
                async with session.get(cap_url) as response:
                    if response.status != 200:
                        return {}
                    
                    cap_xml = await response.text()
                    return self._parse_cap_xml(cap_xml)
                    
        except (asyncio.TimeoutError, aiohttp.ClientError) as err:
            _LOGGER.debug(f"Could not fetch CAP from {cap_url}: {err}")
            return {}

    def _parse_cap_xml(self, cap_xml: str) -> dict[str, Any]:
        """Parse CAP XML to extract details."""
        try:
            namespaces = {'cap': 'urn:oasis:names:tc:emergency:cap:1.2'}
            root = ET.fromstring(cap_xml)
            
            cap_data = {
                "identifier": self._get_xml_text(root, './/cap:identifier', namespaces),
                "sent": self._get_xml_text(root, './/cap:sent', namespaces),
                "onset": self._get_xml_text(root, './/cap:onset', namespaces),
                "expires": self._get_xml_text(root, './/cap:expires', namespaces),
                "severity": self._get_xml_text(root, './/cap:severity', namespaces),
                "certainty": self._get_xml_text(root, './/cap:certainty', namespaces),
                "urgency": self._get_xml_text(root, './/cap:urgency', namespaces),
                "headline": self._get_xml_text(root, './/cap:headline', namespaces),
                "description": self._get_xml_text(root, './/cap:description', namespaces),
                "regions": []
            }
            
            # Extract FIPS region codes
            for geocode in root.findall('.//cap:geocode', namespaces):
                value_name = geocode.find('cap:valueName', namespaces)
                value = geocode.find('cap:value', namespaces)
                
                if value_name is not None and value is not None:
                    if value_name.text == 'FIPS':
                        cap_data["regions"].append(value.text.strip())
            
            return cap_data
            
        except ET.ParseError as err:
            _LOGGER.debug(f"CAP XML parse error: {err}")
            return {}

    def _get_xml_text(self, root, path: str, namespaces: dict) -> str:
        """Safely get text from XML element."""
        element = root.find(path, namespaces)
        return element.text.strip() if element is not None and element.text else ""

    def _process_warnings_data(self, data: dict) -> dict[str, Any]:
        """Process raw API data into structured format."""
        processed_data = {
            "warnings": [],
            "active_warnings_count": 0,
            "highest_warning_level": None,
            "warning_types": set(),
            "regions_affected": set()
        }

        if not data:
            return processed_data

        warnings_list = data if isinstance(data, list) else []

        for warning_data in warnings_list:
            warning = {
                "id": warning_data.get("id"),
                "cap_id": warning_data.get("capId") or warning_data.get("cap_id"),
                "type": warning_data.get("type"),
                "level": warning_data.get("level"),
                "issued": warning_data.get("issued"),
                "updated": warning_data.get("updated"),
                "onset": warning_data.get("onset"),
                "expires": warning_data.get("expiry") or warning_data.get("expires"),
                "headline": warning_data.get("headline"),
                "description": warning_data.get("description"),
                "instruction": warning_data.get("instruction"),
                "regions": warning_data.get("regions", []),
                "severity": warning_data.get("severity"),
                "certainty": warning_data.get("certainty"),
                "urgency": warning_data.get("urgency"),
                "status": warning_data.get("status", "").lower()
            }
            
            if self._should_include_warning(warning):
                processed_data["warnings"].append(warning)
                
                if warning["status"] in ["warning", "actual", "active"]:
                    processed_data["active_warnings_count"] += 1
                    
                    if warning["type"]:
                        processed_data["warning_types"].add(warning["type"])
                    if warning["regions"]:
                        processed_data["regions_affected"].update(warning["regions"])
                    
                    level = warning.get("level", "").lower()
                    if level in ["red", "orange", "yellow"]:
                        if processed_data["highest_warning_level"] is None:
                            processed_data["highest_warning_level"] = level
                        elif level == "red":
                            processed_data["highest_warning_level"] = "red"
                        elif level == "orange" and processed_data["highest_warning_level"] != "red":
                            processed_data["highest_warning_level"] = "orange"

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
        
        from .const import REGION_CODES
        warning_counties = []
        for code in warning_region_codes:
            county = REGION_CODES.get(code)
            if county:
                warning_counties.append(county)
        
        if area_type == "regions":
            selected_regions = area_config.get("selected_regions", [])
            
            from .const import REGION_TO_COUNTIES
            for selected_region in selected_regions:
                region_counties = REGION_TO_COUNTIES.get(selected_region, [])
                for warning_county in warning_counties:
                    if warning_county in region_counties:
                        return True
            return False
            
        elif area_type == "counties":
            selected_counties = area_config.get("selected_counties", [])
            
            for warning_county in warning_counties:
                if warning_county in selected_counties:
                    return True
            return False
            
        return True