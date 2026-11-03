"""Entry setup, unload/reload, and stable entity IDs."""

from __future__ import annotations

from copy import deepcopy
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
        "hardware": "WXM-WG1200",
        "device_name": "Test Gateway",
        "firmware": "0.8.39",
        "api_version": "1.0.0",
        "mac": "02:11:22:33:44:55",
        "uptime_sec": 4321,
        "wifi": {"status": "CONNECTED", "rssi": -58, "ip": "192.0.2.45"},
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
    status = {
        "wifi_status": "CONNECTED",
        "mqtt_status": "CONNECTED",
        "mqtt_success_count": 50,
        "mqtt_fail_count": 2,
        "lora_link_ok": True,
        "is_paired": True,
        "uplink_active": True,
        "uptime_sec": 4321,
        "rx_packet_total": 400,
        "activity_status": "ACTIVE_OK",
        "pairing_state": "PAIRED",
        "ownership_status": "confirmed",
        "listen_freq_hz": 868350000,
        "sd_present": True,
        "sd_mounted": True,
        "sd_unusable": False,
        "sd_capacity_gb": 16.0,
        "sd_fs_type": "FAT32",
        "sd_status_reason": "mounted",
        "paired_id": 19,
        "recent_stations": [
            {"id": 19, "rssi": -70, "snr": -4, "age_sec": 10},
            {"id": 20, "rssi": -90, "snr": -9, "age_sec": 5},
        ],
    }

    async def get_info(api: GatewayApi) -> dict:
        """Return unique sanitized identity metadata for each mock gateway."""
        payload = deepcopy(info)
        if api.host == "192.168.1.23":
            payload.update(
                gateway_id="WXM-SECOND-GATEWAY",
                device_name="Second Gateway",
                mac="02:11:22:33:44:56",
            )
        return payload

    with (
        patch.object(GatewayApi, "async_get_info", autospec=True, side_effect=get_info),
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
        for key in (
            "gateway_uptime",
            "rx_packet_total",
            "mqtt_success_count",
            "mqtt_fail_count",
            "station_packet_age",
        ):
            entity = next(
                item
                for item in registry.entities.values()
                if item.unique_id == f"WXM-LIFECYCLE_{key}"
            )
            assert entity.disabled_by == er.RegistryEntryDisabler.INTEGRATION
        device_registry = dr.async_get(hass)
        gateway_device = device_registry.async_get_device_by_identifier(
            (DOMAIN, "WXM-LIFECYCLE"), entry.entry_id
        )
        assert gateway_device is not None
        gateway_device = device_registry.async_update_device(
            gateway_device.id, name_by_user="My Weather Gateway"
        )
        assert gateway_device is not None
        assert gateway_device.name_by_user == "My Weather Gateway"
        assert gateway_device.manufacturer == "WeatherXM"
        assert gateway_device.model == "WXM-WG1200"
        assert gateway_device.model_id == "WXM-WG1200"
        assert gateway_device.hw_version is None
        assert gateway_device.sw_version == "0.8.39"
        assert gateway_device.serial_number == "WXM-LIFECYCLE"
        assert gateway_device.connections == {
            (dr.CONNECTION_NETWORK_MAC, "02:11:22:33:44:55")
        }
        assert gateway_device.configuration_url == "http://gateway.local:80/"
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
        assert (
            dr.async_get(hass)
            .async_get_device_by_identifier((DOMAIN, "WXM-LIFECYCLE"), entry.entry_id)
            .configuration_url
            == "http://192.168.1.22:80/"
        )
        refreshed_device = dr.async_get(hass).async_get_device_by_identifier(
            (DOMAIN, "WXM-LIFECYCLE"), entry.entry_id
        )
        assert refreshed_device is not None
        assert refreshed_device.name_by_user == "My Weather Gateway"

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
