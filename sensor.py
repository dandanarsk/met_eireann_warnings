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
        self._attr_name = "Met Éireann Active Warnings Count"
        self._attr_unique_id = f"{DOMAIN}_active_warnings_count"
        self._attr_icon = "mdi:weather-cloudy-alert"
        self._attr_device_class = SensorDeviceClass.ENUM
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> int:
        """Return the state of the sensor."""
        return self.coordinator.data.get("active_warnings_count", 0)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        data = self.coordinator.data
        return {
            "warning_types": data.get("warning_types", []),
            "regions_affected": data.get("regions_affected", []),
            "last_updated": datetime.now().isoformat(),
        }


class MetEireannHighestLevelSensor(CoordinatorEntity, SensorEntity):
    """Sensor for the highest active warning level."""

    def __init__(self, coordinator: MetEireannDataUpdateCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_name = "Met Éireann Highest Warning Level"
        self._attr_unique_id = f"{DOMAIN}_highest_warning_level"

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
        attributes = {
            "active_warnings_count": self.coordinator.data.get("active_warnings_count", 0),
            "last_updated": datetime.now().isoformat(),
        }
        
        if level and level in WARNING_LEVELS:
            attributes.update({
                "color": WARNING_LEVELS[level]["color"],
                "priority": WARNING_LEVELS[level]["priority"]
            })
        
        return attributes


class MetEireannActiveWarningsSensor(CoordinatorEntity, SensorEntity):
    """Sensor containing detailed information about active warnings."""

    def __init__(self, coordinator: MetEireannDataUpdateCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_name = "Met Éireann Active Warnings"
        self._attr_unique_id = f"{DOMAIN}_active_warnings"
        self._attr_icon = "mdi:format-list-bulleted"

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
            if warning.get("status", "").lower() in ["actual", "active"]
        ]
        
        attributes = {
            "active_warnings_count": len(active_warnings),
            "total_warnings": len(warnings),
            "warning_types": self.coordinator.data.get("warning_types", []),
            "regions_affected": self.coordinator.data.get("regions_affected", []),
            "last_updated": datetime.now().isoformat(),
            "warnings": []
        }
        
        # Add detailed warning information
        for warning in active_warnings:
            warning_info = {
                "id": warning.get("id"),
                "type": warning.get("type"),
                "level": warning.get("level"),
                "headline": warning.get("headline"),
                "onset": warning.get("onset"),
                "expires": warning.get("expires"),
                "regions": warning.get("regions", []),
                "severity": warning.get("severity"),
                "certainty": warning.get("certainty"),
                "urgency": warning.get("urgency")
            }
            attributes["warnings"].append(warning_info)
        
        return attributes