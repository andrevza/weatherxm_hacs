"""Privacy and failure handling for downloaded gateway diagnostics."""

from __future__ import annotations

import json
import time
from datetime import timedelta
from types import SimpleNamespace

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.weatherxm_gateway.const import DOMAIN
from custom_components.weatherxm_gateway.diagnostics import (
    async_get_config_entry_diagnostics,
    async_get_device_diagnostics,
)


def _coordinator(data: dict, *, success: bool = True) -> SimpleNamespace:
    """Create the coordinator subset used by the diagnostics builder."""
    return SimpleNamespace(
        data=data,
        update_interval=timedelta(seconds=60),
        last_update_success=success,
        last_update_success_time=None,
    )


def _entry(hass: HomeAssistant, gateway_key: str, rssi: int) -> MockConfigEntry:
    """Add a sanitized entry whose responses contain representative secrets."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=gateway_key,
        data={"host": "192.0.2.90", "port": 8080},
    )
    entry.add_to_hass(hass)
    info = {
        "gateway_id": gateway_key,
        "id": gateway_key,
        "model": "WXM-WG1200",
        "hardware": "WXM-WG1200",
        "firmware": "0.8.39",
        "api_version": "1.0.0",
        "device_name": "Private Home Gateway",
        "mac": "02:AA:BB:CC:DD:EE",
        "uptime_sec": 3600,
        "wifi": {
            "status": "CONNECTED",
            "ssid": "SecretNetworkName",
            "ip": "192.0.2.91",
            "rssi": rssi,
        },
        "station": {
            "paired_id": 123456,
            "is_paired": True,
            "station_type": 1001,
            "station_fw_version": 0,
            "packet_reception": 98,
        },
        "location": {"latitude": -26.0, "longitude": 28.0},
    }
    status = {
        "mqtt_status": "CONNECTED",
        "mqtt_success_count": 29,
        "mqtt_fail_count": 1,
        "active_link": True,
        "lora_link_ok": True,
        "uplink_active": True,
        "uplink_enabled": True,
        "activity_status": "ACTIVE_OK",
        "is_paired": True,
        "paired_id": 123456,
        "pairing_state": "PAIRED",
        "ownership_status": "confirmed",
        "listen_freq_hz": 868350000,
        "rx_packet_total": 800,
        "recent_stations": [
            {
                "id": 123456,
                "age_sec": 12,
                "rssi": -72,
                "snr": -3,
                "channel_slot": 1,
                "pubkey": "PRIVATE-PUBLIC-KEY",
            }
        ],
        "sd_present": True,
        "sd_mounted": True,
        "sd_unusable": False,
        "sd_capacity_gb": 32.0,
        "sd_fs_type": "FAT32",
        "sd_status_reason": "mounted",
    }
    observations = {
        "has_weather": True,
        "timestamp": int(time.time()),
        "temp": 20.0,
        "feels_like": 20.0,
        "humidity": 60.0,
        "pressure": 1012.0,
        "wind_speed": 1.0,
        "wind_gust": 2.0,
        "wind_dir_deg": 0.0,
        "precip_rate": 0.0,
        "precip_daily": 0.0,
        "precip_24h": 0.0,
        "precip_cml": 1.0,
        "uv": 0.0,
        "irradiance": 0.0,
        "internal_secret": "DO-NOT-EXPORT",
    }
    entry.runtime_data = SimpleNamespace(
        weather=_coordinator(observations),
        diagnostics=_coordinator({"info": info, "status": status}),
    )
    return entry


async def test_config_and_device_diagnostics_are_redacted_and_serializable(
    hass: HomeAssistant, enable_custom_integrations: None
) -> None:
    """Only safe allowlisted values leave diagnostics, as JSON."""
    entry = _entry(hass, "PRIVATE-GATEWAY-ID", -38)
    output = await async_get_config_entry_diagnostics(hass, entry)
    encoded = json.dumps(output)

    assert output["device"]["model"] == "WXM-WG1200"
    assert output["device"]["wifi"]["rssi"] == -38
    assert output["device"]["station_radio"] == {
        "rssi": -72,
        "snr": -3,
        "age_sec": 12,
        "channel_slot": 1,
    }
    assert output["device"]["uptime_sec"] == 3600
    assert output["device"]["sd_capacity_gb"] == 32.0
    assert output["device"]["sd_status_reason"] == "mounted"
    assert output["observations"]["wind_dir_deg"] == 0.0
    assert output["integration"]["observation_freshness"] == "current"
    assert output["integration"]["weather_api"]["last_update_success"] is True
    for secret in (
        "PRIVATE-GATEWAY-ID",
        "SecretNetworkName",
        "192.0.2.90",
        "192.0.2.91",
        "02:AA:BB:CC:DD:EE",
        "Private Home Gateway",
        "PRIVATE-PUBLIC-KEY",
        "DO-NOT-EXPORT",
        "123456",
    ):
        assert secret not in encoded

    registry = dr.async_get(hass)
    device = registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.unique_id)},
    )
    device_output = await async_get_device_diagnostics(hass, entry, device)
    assert device_output["device"] == output["device"]
    other = registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "OTHER-GATEWAY")},
    )
    assert await async_get_device_diagnostics(hass, entry, other) == {}

    entry.runtime_data.diagnostics.data["status"]["sd_status_reason"] = (
        "SecretNetworkName"
    )
    redacted_reason = await async_get_config_entry_diagnostics(hass, entry)
    assert redacted_reason["device"]["sd_status_reason"] is None


async def test_diagnostics_remain_valid_with_failed_empty_coordinators(
    hass: HomeAssistant, enable_custom_integrations: None
) -> None:
    """A failed or not-yet-populated entry still produces valid JSON."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="EMPTY-GATEWAY",
        data={"host": "gateway.local", "port": 80},
    )
    entry.add_to_hass(hass)
    entry.runtime_data = SimpleNamespace(
        weather=_coordinator({}, success=False),
        diagnostics=_coordinator({}, success=False),
    )
    output = await async_get_config_entry_diagnostics(hass, entry)
    json.dumps(output)
    assert output["device"]["station_radio"] == {}
    assert output["available_fields"]["status"]["present"] == []
    assert output["integration"]["observation_freshness"] == "unavailable"
    assert output["integration"]["weather_api"]["last_update_success"] is False


async def test_diagnostics_are_isolated_between_gateways(
    hass: HomeAssistant, enable_custom_integrations: None
) -> None:
    """Each config entry's export uses only its own coordinator data."""
    first = _entry(hass, "GATEWAY-ONE", -31)
    second = _entry(hass, "GATEWAY-TWO", -62)
    first_data = await async_get_config_entry_diagnostics(hass, first)
    second_data = await async_get_config_entry_diagnostics(hass, second)
    assert first_data["device"]["wifi"]["rssi"] == -31
    assert second_data["device"]["wifi"]["rssi"] == -62
    assert first_data["device"] != second_data["device"]
