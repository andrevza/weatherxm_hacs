"""Entry setup, unload/reload, and stable entity IDs."""

from __future__ import annotations

from time import time
from unittest.mock import patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.weatherxm_gateway.api import GatewayApi
from custom_components.weatherxm_gateway.const import DOMAIN
from custom_components.weatherxm_gateway.coordinator import WeatherCoordinator


async def test_entry_unload_reload_and_stable_entity_ids(
    hass: HomeAssistant, enable_custom_integrations: None
) -> None:
    """Load and unload all platforms cleanly while retaining unique IDs."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="WXM-LIFECYCLE",
        data={"host": "gateway.local", "port": 80},
    )
    entry.add_to_hass(hass)
    info = {
        "gateway_id": "WXM-LIFECYCLE",
        "model": "WXM-WG1200",
        "device_name": "Test Gateway",
        "firmware": "0.8.39",
        "api_version": "1.0.0",
        "wifi": {"status": "CONNECTED", "rssi": -58},
        "station": {"packet_reception": 99, "paired_id": 19, "station_type": 1001},
    }
    observations = {
        "has_weather": True,
        "timestamp": int(time()),
        "temp": 20.0,
        "feels_like": 20.0,
        "humidity": 50.0,
        "pressure": 1013.0,
        "wind_speed": 0.0,
        "wind_gust": 1.0,
        "wind_dir_deg": 0.0,
        "precip_rate": 0.0,
        "precip_daily": 0.0,
        "precip_24h": 0.0,
        "precip_cml": 10.0,
        "uv": 1,
        "irradiance": 100.0,
    }
    status = {"wifi_status": "CONNECTED", "lora_link_ok": True}
    with (
        patch.object(GatewayApi, "async_get_info", return_value=info),
        patch.object(GatewayApi, "async_get_observations", return_value=observations),
        patch.object(GatewayApi, "async_get_status", return_value=status),
        patch(
            "custom_components.weatherxm_gateway.async_get_clientsession",
            return_value=object(),
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        registry = er.async_get(hass)
        assert any(
            item.unique_id == "WXM-LIFECYCLE_temperature"
            for item in registry.entities.values()
        )
        assert any(
            item.unique_id == "WXM-LIFECYCLE_weather"
            for item in registry.entities.values()
        )
        timestamp_entity = next(
            item
            for item in registry.entities.values()
            if item.unique_id == "WXM-LIFECYCLE_observation_timestamp"
        )
        assert timestamp_entity.entity_id == "sensor.test_gateway_latest_observation"
        assert timestamp_entity.disabled_by == er.RegistryEntryDisabler.INTEGRATION
        registry.async_update_entity(timestamp_entity.entity_id, disabled_by=None)
        assert await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()
        assert hass.states.get(timestamp_entity.entity_id) is not None
        weather_state = next(state for state in hass.states.async_all("weather"))
        assert weather_state.attributes["wind_bearing"] == 0
        assert weather_state.attributes.get("condition") is None
        assert "forecast" not in weather_state.attributes
        hass.config_entries.async_update_entry(
            entry, data={"host": "192.168.1.22", "port": 80}
        )
        await hass.async_block_till_done()
        assert entry.runtime_data.api.host == "192.168.1.22"

        second = MockConfigEntry(
            domain=DOMAIN,
            unique_id="WXM-SECOND-GATEWAY",
            data={"host": "192.168.1.23", "port": 80},
        )
        second.add_to_hass(hass)
        assert await hass.config_entries.async_setup(second.entry_id)
        await hass.async_block_till_done()
        unique_ids = {
            item.unique_id
            for item in er.async_get(hass).entities.values()
            if item.unique_id.endswith("_temperature")
        }
        assert unique_ids == {
            "WXM-LIFECYCLE_temperature",
            "WXM-SECOND-GATEWAY_temperature",
        }
        device_registry = dr.async_get(hass)
        gateway_devices = dr.async_entries_for_config_entry(
            device_registry, entry.entry_id
        ) + dr.async_entries_for_config_entry(device_registry, second.entry_id)
        assert len(gateway_devices) == 2

        assert await hass.config_entries.async_unload(second.entry_id)
        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert (
        sum(
            item.unique_id == "WXM-LIFECYCLE_temperature"
            for item in er.async_get(hass).entities.values()
        )
        == 1
    )


@pytest.mark.parametrize("age", [181, 600])
async def test_stale_observation_is_marked_missing(
    hass: HomeAssistant, age: int
) -> None:
    """Old timestamps never leave weather values marked as current."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=f"WXM-STALE-{age}",
        data={"host": "gateway.local", "port": 80},
    )
    api = GatewayApi("gateway.local", 80, object())  # type: ignore[arg-type]
    coordinator = WeatherCoordinator(hass, api, entry)
    with patch.object(
        api,
        "async_get_observations",
        return_value={"has_weather": True, "timestamp": int(time()) - age},
    ):
        data = await coordinator._async_update_data()
    assert data["has_weather"] is False
