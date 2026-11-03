"""WeatherXM WG1200 local integration."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import GatewayApi
from .const import CONF_PORT, DEFAULT_PORT
from .coordinator import DiagnosticCoordinator, WeatherCoordinator

PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR, Platform.WEATHER]


@dataclass
class GatewayRuntimeData:
    """Data shared by platform entities."""

    api: GatewayApi
    weather: WeatherCoordinator
    diagnostics: DiagnosticCoordinator


type GatewayConfigEntry = ConfigEntry[GatewayRuntimeData]


async def async_setup_entry(hass: HomeAssistant, entry: GatewayConfigEntry) -> bool:
    """Set up gateway from a config entry."""
    api = GatewayApi(
        entry.data[CONF_HOST],
        entry.data.get(CONF_PORT, DEFAULT_PORT),
        async_get_clientsession(hass),
    )
    weather = WeatherCoordinator(hass, api, entry)
    diagnostics = DiagnosticCoordinator(hass, api, entry)
    await weather.async_config_entry_first_refresh()
    await diagnostics.async_config_entry_first_refresh()
    entry.runtime_data = GatewayRuntimeData(api, weather, diagnostics)
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def _async_options_updated(
    hass: HomeAssistant, entry: GatewayConfigEntry
) -> None:
    """Reload coordinators when polling options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: GatewayConfigEntry) -> bool:
    """Unload platforms for a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
