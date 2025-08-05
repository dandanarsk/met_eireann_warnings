"""Config flow for Met Éireann Weather Warnings integration."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp
import async_timeout
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import DOMAIN, AREA_OPTIONS, REGIONS, COUNTIES

_LOGGER = logging.getLogger(__name__)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect."""
    session = async_get_clientsession(hass)
    
    try:
        async with async_timeout.timeout(10):
            async with session.get("https://www.met.ie/Open_Data/json/warning_IRELAND.json") as response:
                if response.status != 200:
                    raise CannotConnect
                await response.json()
    except asyncio.TimeoutError:
        raise CannotConnect
    except aiohttp.ClientError:
        raise CannotConnect

    return {"title": "Met Éireann Weather Warnings"}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Met Éireann Weather Warnings."""

    VERSION = 1

    def __init__(self):
        """Initialize the config flow."""
        self.config_data = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
                self.config_data.update(user_input)
                
                # Move to area selection step
                return await self.async_step_area()
                
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        # Initial configuration schema
        schema = vol.Schema({
            vol.Optional("polling_interval", default=30): vol.All(
                vol.Coerce(int), vol.Range(min=10, max=120)
            ),
        })

        return self.async_show_form(
            step_id="user", 
            data_schema=schema, 
            errors=errors
        )

    async def async_step_area(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle area selection step."""
        errors: dict[str, str] = {}
        
        if user_input is not None:
            area_type = user_input["area_type"]
            self.config_data["area_type"] = area_type
            
            if area_type == "whole_ireland":
                # No further selection needed
                return self.async_create_entry(
                    title="Met Éireann Weather Warnings", 
                    data=self.config_data
                )
            elif area_type == "regions":
                return await self.async_step_regions()
            elif area_type == "counties":
                return await self.async_step_counties()

        # Area type selection schema
        schema = vol.Schema({
            vol.Required("area_type"): SelectSelector(
                SelectSelectorConfig(
                    options=[
                        {"value": "whole_ireland", "label": "Whole Ireland"},
                        {"value": "regions", "label": "Select Regions"},
                        {"value": "counties", "label": "Select Counties"},
                    ],
                    mode=SelectSelectorMode.DROPDOWN,
                )
            ),
        })

        return self.async_show_form(
            step_id="area",
            data_schema=schema,
            errors=errors
        )

    async def async_step_regions(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle region selection step."""
        if user_input is not None:
            selected_regions = user_input["selected_regions"]
            if not selected_regions:
                return self.async_show_form(
                    step_id="regions",
                    data_schema=self._get_regions_schema(),
                    errors={"selected_regions": "Please select at least one region"}
                )
            
            self.config_data["selected_regions"] = selected_regions
            return self.async_create_entry(
                title="Met Éireann Weather Warnings", 
                data=self.config_data
            )

        return self.async_show_form(
            step_id="regions",
            data_schema=self._get_regions_schema()
        )

    async def async_step_counties(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle county selection step."""
        if user_input is not None:
            selected_counties = user_input["selected_counties"]
            if not selected_counties:
                return self.async_show_form(
                    step_id="counties",
                    data_schema=self._get_counties_schema(),
                    errors={"selected_counties": "Please select at least one county"}
                )
            
            self.config_data["selected_counties"] = selected_counties
            return self.async_create_entry(
                title="Met Éireann Weather Warnings", 
                data=self.config_data
            )

        return self.async_show_form(
            step_id="counties",
            data_schema=self._get_counties_schema()
        )

    def _get_regions_schema(self):
        """Get the regions selection schema."""
        region_options = [
            {"value": key, "label": value} for key, value in REGIONS.items()
        ]
        
        return vol.Schema({
            vol.Required("selected_regions"): SelectSelector(
                SelectSelectorConfig(
                    options=region_options,
                    mode=SelectSelectorMode.DROPDOWN,
                    multiple=True,
                )
            ),
        })

    def _get_counties_schema(self):
        """Get the counties selection schema."""
        county_options = [
            {"value": key, "label": value} for key, value in COUNTIES.items()
        ]
        
        return vol.Schema({
            vol.Required("selected_counties"): SelectSelector(
                SelectSelectorConfig(
                    options=county_options,
                    mode=SelectSelectorMode.DROPDOWN,
                    multiple=True,
                )
            ),
        })


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""
