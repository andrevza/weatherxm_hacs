"""WeatherXM WG1200 local integration."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import GatewayApi
from .const import CONF_PORT, DEFAULT_PORT, DOMAIN
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
    entry.async_on_unload(
        diagnostics.async_add_listener(lambda: _refresh_device_registry(hass, entry))
    )
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


def _refresh_device_registry(hass: HomeAssistant, entry: GatewayConfigEntry) -> None:
    """Refresh reported metadata without replacing the gateway's stable identity."""
    from .entity import device_info

    registry = dr.async_get(hass)
    identifier = (DOMAIN, entry.unique_id)
    device = registry.async_get_device_by_identifier(identifier, entry.entry_id)
    if device is None:
        return
    data = entry.runtime_data.diagnostics.data or {}
    info = data.get("info", {})
    details = device_info(entry, info if isinstance(info, dict) else {})
    updates = {
        key: details[key]
        for key in (
            "configuration_url",
            "manufacturer",
            "model",
            "model_id",
            "name",
            "serial_number",
            "sw_version",
        )
        if key in details
    }
    if details.get("connections"):
        updates["new_connections"] = details["connections"]
    registry.async_update_device(device.id, **updates)


async def _async_options_updated(
    hass: HomeAssistant, entry: GatewayConfigEntry
) -> None:
    """Reload coordinators when polling options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: GatewayConfigEntry) -> bool:
    """Unload platforms for a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
