"""Sensor platform for Met Éireann Weather Warnings."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import MetEireannDataUpdateCoordinator
from .const import DOMAIN, WARNING_LEVELS


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the sensor platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    entities = [
        MetEireannWarningsCountSensor(coordinator),
        MetEireannHighestLevelSensor(coordinator),
        MetEireannActiveWarningsSensor(coordinator)
    ]

    async_add_entities(entities)


class MetEireannWarningsCountSensor(CoordinatorEntity, SensorEntity):
    """Sensor for the count of active weather warnings."""

    def __init__(self, coordinator: MetEireannDataUpdateCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        
        # Generate descriptive names based on area configuration
        area_suffix = self._get_area_suffix()
        self._attr_name = f"Met Éireann Active Warnings Count{area_suffix}"
        self._attr_unique_id = f"{DOMAIN}_active_warnings_count{area_suffix.lower().replace(' ', '_').replace('(', '').replace(')', '')}"
        self._attr_icon = "mdi:weather-cloudy-alert"
        self._attr_device_class = SensorDeviceClass.ENUM
        self._attr_state_class = SensorStateClass.MEASUREMENT

    def _get_area_suffix(self) -> str:
        """Get area suffix for sensor name."""
        area_config = getattr(self.coordinator, 'area_config', {})
        area_type = area_config.get("area_type", "whole_ireland")
        
        if area_type == "whole_ireland":
            return " (Ireland)"
        elif area_type == "regions":
            regions = area_config.get("selected_regions", [])
            if len(regions) == 1:
                from .const import REGIONS
                return f" ({REGIONS.get(regions[0], regions[0]).title()})"
            else:
                return f" ({len(regions)} Regions)"
        elif area_type == "counties":
            counties = area_config.get("selected_counties", [])
            if len(counties) == 1:
                from .const import COUNTIES
                return f" ({COUNTIES.get(counties[0], counties[0]).title()})"
            else:
                return f" ({len(counties)} Counties)"
        return ""

    @property
    def native_value(self) -> int:
        """Return the state of the sensor."""
        return self.coordinator.data.get("active_warnings_count", 0)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        data = self.coordinator.data
        area_config = getattr(self.coordinator, 'area_config', {})
        
        # Convert region codes to county names for display
        from .const import REGION_CODES, COUNTIES
        region_names = []
        for code in data.get("regions_affected", []):
            county = REGION_CODES.get(code)
            if county:
                county_name = COUNTIES.get(county, county)
                region_names.append(county_name)
        
        attributes = {
            "warning_types": data.get("warning_types", []),
            "regions_affected": region_names,
            "region_codes_affected": data.get("regions_affected", []),
            "last_updated": datetime.now().isoformat(),
            "area_type": area_config.get("area_type", "whole_ireland"),
        }
        
        # Add configured areas to attributes
        if area_config.get("area_type") == "regions":
            attributes["monitored_regions"] = area_config.get("selected_regions", [])
        elif area_config.get("area_type") == "counties":
            attributes["monitored_counties"] = area_config.get("selected_counties", [])
            
        return attributes


class MetEireannHighestLevelSensor(CoordinatorEntity, SensorEntity):
    """Sensor for the highest active warning level."""

    def __init__(self, coordinator: MetEireannDataUpdateCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        
        # Generate descriptive names based on area configuration
        area_suffix = self._get_area_suffix()
        self._attr_name = f"Met Éireann Highest Warning Level{area_suffix}"
        self._attr_unique_id = f"{DOMAIN}_highest_warning_level{area_suffix.lower().replace(' ', '_').replace('(', '').replace(')', '')}"

    def _get_area_suffix(self) -> str:
        """Get area suffix for sensor name."""
        area_config = getattr(self.coordinator, 'area_config', {})
        area_type = area_config.get("area_type", "whole_ireland")
        
        if area_type == "whole_ireland":
            return " (Ireland)"
        elif area_type == "regions":
            regions = area_config.get("selected_regions", [])
            if len(regions) == 1:
                from .const import REGIONS
                return f" ({REGIONS.get(regions[0], regions[0]).title()})"
            else:
                return f" ({len(regions)} Regions)"
        elif area_type == "counties":
            counties = area_config.get("selected_counties", [])
            if len(counties) == 1:
                from .const import COUNTIES
                return f" ({COUNTIES.get(counties[0], counties[0]).title()})"
            else:
                return f" ({len(counties)} Counties)"
        return ""

    @property
    def native_value(self) -> str | None:
        """Return the state of the sensor."""
        level = self.coordinator.data.get("highest_warning_level")
        return level.title() if level else "None"

    @property
    def icon(self) -> str:
        """Return the icon of the sensor."""
        level = self.coordinator.data.get("highest_warning_level")
        if level and level in WARNING_LEVELS:
            return WARNING_LEVELS[level]["icon"]
        return "mdi:weather-sunny"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        level = self.coordinator.data.get("highest_warning_level")
        area_config = getattr(self.coordinator, 'area_config', {})
        
        attributes = {
            "active_warnings_count": self.coordinator.data.get("active_warnings_count", 0),
            "last_updated": datetime.now().isoformat(),
            "area_type": area_config.get("area_type", "whole_ireland"),
        }
        
        if level and level in WARNING_LEVELS:
            attributes.update({
                "color": WARNING_LEVELS[level]["color"],
                "priority": WARNING_LEVELS[level]["priority"]
            })
        
        # Add configured areas to attributes
        if area_config.get("area_type") == "regions":
            attributes["monitored_regions"] = area_config.get("selected_regions", [])
        elif area_config.get("area_type") == "counties":
            attributes["monitored_counties"] = area_config.get("selected_counties", [])
        
        return attributes


class MetEireannActiveWarningsSensor(CoordinatorEntity, SensorEntity):
    """Sensor containing detailed information about active warnings."""

    def __init__(self, coordinator: MetEireannDataUpdateCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        
        # Generate descriptive names based on area configuration
        area_suffix = self._get_area_suffix()
        self._attr_name = f"Met Éireann Active Warnings{area_suffix}"
        self._attr_unique_id = f"{DOMAIN}_active_warnings{area_suffix.lower().replace(' ', '_').replace('(', '').replace(')', '')}"
        self._attr_icon = "mdi:format-list-bulleted"

    def _get_area_suffix(self) -> str:
        """Get area suffix for sensor name."""
        area_config = getattr(self.coordinator, 'area_config', {})
        area_type = area_config.get("area_type", "whole_ireland")
        
        if area_type == "whole_ireland":
            return " (Ireland)"
        elif area_type == "regions":
            regions = area_config.get("selected_regions", [])
            if len(regions) == 1:
                from .const import REGIONS
                return f" ({REGIONS.get(regions[0], regions[0]).title()})"
            else:
                return f" ({len(regions)} Regions)"
        elif area_type == "counties":
            counties = area_config.get("selected_counties", [])
            if len(counties) == 1:
                from .const import COUNTIES
                return f" ({COUNTIES.get(counties[0], counties[0]).title()})"
            else:
                return f" ({len(counties)} Counties)"
        return ""

    @property
    def native_value(self) -> str:
        """Return the state of the sensor."""
        active_count = self.coordinator.data.get("active_warnings_count", 0)
        if active_count == 0:
            return "No active warnings"
        elif active_count == 1:
            return "1 active warning"
        else:
            return f"{active_count} active warnings"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return detailed information about active warnings."""
        warnings = self.coordinator.data.get("warnings", [])
        active_warnings = [
            warning for warning in warnings 
            if warning.get("status", "").lower() in ["warning", "actual", "active"]
        ]
        
        area_config = getattr(self.coordinator, 'area_config', {})
        
        # Convert region codes to county names for display
        from .const import REGION_CODES, COUNTIES
        regions_affected = []
        for code in self.coordinator.data.get("regions_affected", []):
            county = REGION_CODES.get(code)
            if county:
                county_name = COUNTIES.get(county, county)
                regions_affected.append(county_name)
        
        attributes = {
            "active_warnings_count": len(active_warnings),
            "total_warnings": len(warnings),
            "warning_types": self.coordinator.data.get("warning_types", []),
            "regions_affected": regions_affected,
            "region_codes_affected": self.coordinator.data.get("regions_affected", []),
            "last_updated": datetime.now().isoformat(),
            "area_type": area_config.get("area_type", "whole_ireland"),
            "warnings": []
        }
        
        # Add configured areas to attributes
        if area_config.get("area_type") == "regions":
            attributes["monitored_regions"] = area_config.get("selected_regions", [])
        elif area_config.get("area_type") == "counties":
            attributes["monitored_counties"] = area_config.get("selected_counties", [])
        
        # Add detailed warning information
        for warning in active_warnings:
            # Convert region codes to county names for display
            region_names = []
            for code in warning.get("regions", []):
                county = REGION_CODES.get(code)
                if county:
                    county_name = COUNTIES.get(county, county)
                    region_names.append(county_name)
            
            warning_info = {
                "id": warning.get("id"),
                "cap_id": warning.get("cap_id"),
                "type": warning.get("type"),
                "level": warning.get("level"),
                "issued": warning.get("issued"),
                "updated": warning.get("updated"),
                "headline": warning.get("headline"),
                "description": warning.get("description"),
                "onset": warning.get("onset"),
                "expires": warning.get("expires"),
                "regions": region_names,  # Use converted county names
                "region_codes": warning.get("regions", []),  # Keep original codes for reference
                "severity": warning.get("severity"),
                "certainty": warning.get("certainty"),
                "urgency": warning.get("urgency"),
                "status": warning.get("status")
            }
            attributes["warnings"].append(warning_info)
        
        return attributes
