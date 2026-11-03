"""Tests for measurement metadata and diagnostic field selection."""

from __future__ import annotations

import pytest
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.weatherxm_gateway.binary_sensor import (
    binary_sensor_available,
    binary_sensor_value,
)
from custom_components.weatherxm_gateway.const import DOMAIN
from custom_components.weatherxm_gateway.entity import configuration_url, device_info
from custom_components.weatherxm_gateway.sensor import (
    DIAGNOSTIC_SENSORS,
    WEATHER_SENSORS,
    DiagnosticDescription,
    _diagnostic_available,
    diagnostic_native_value,
)


def test_daily_and_rolling_rain_are_measurements() -> None:
    """Daily reset and rolling-window decrease must not be total-increasing."""
    descriptions = {description.key: description for description in WEATHER_SENSORS}
    assert descriptions["daily_rainfall"].state_class == SensorStateClass.MEASUREMENT
    assert descriptions["rolling_rainfall"].state_class == SensorStateClass.MEASUREMENT
    assert (
        descriptions["lifetime_rainfall"].state_class
        == SensorStateClass.TOTAL_INCREASING
    )


def test_zero_wind_direction_is_a_valid_measurement() -> None:
    """North is not filtered or rewritten as missing."""
    direction = next(item for item in WEATHER_SENSORS if item.key == "wind_direction")
    assert direction.state_class == SensorStateClass.MEASUREMENT_ANGLE
    assert direction.native_unit_of_measurement == "°"


def test_packet_reception_prefers_confirmed_field_and_supports_legacy() -> None:
    """Create packet reception diagnostics when either known field is present."""
    description = next(
        item for item in DIAGNOSTIC_SENSORS if item.key == "packet_reception"
    )
    assert isinstance(description, DiagnosticDescription)
    assert _diagnostic_available(
        {"info": {"station": {"packet_reception": 95}}, "status": {}}, description
    )
    assert _diagnostic_available(
        {"info": {"station": {"reception": 95}}, "status": {}}, description
    )
    assert (
        diagnostic_native_value(
            description, {"station": {"packet_reception": 96, "reception": 95}}, {}, {}
        )
        == 96
    )
    assert (
        diagnostic_native_value(description, {"station": {"reception": 95}}, {}, {})
        == 95
    )
    assert diagnostic_native_value(description, {}, {"packet_reception": 94}, {}) == 94


def test_diagnostics_without_source_fields_are_not_created() -> None:
    """Avoid creating diagnostics from unavailable or invented payload fields."""
    description = next(item for item in DIAGNOSTIC_SENSORS if item.key == "station_snr")
    assert not _diagnostic_available(
        {"info": {}, "status": {"recent_stations": []}}, description
    )


def test_latest_observation_is_disabled_by_default() -> None:
    """Keep the timestamp available without filling Activity every poll."""
    description = next(
        item for item in DIAGNOSTIC_SENSORS if item.key == "observation_timestamp"
    )
    assert description.device_class == SensorDeviceClass.TIMESTAMP
    assert description.entity_registry_enabled_default is False


def test_fast_or_advanced_diagnostics_are_disabled_by_default() -> None:
    """Opt-in changing values while leaving useful health diagnostics enabled."""
    descriptions = {item.key: item for item in DIAGNOSTIC_SENSORS}
    disabled = {
        "gateway_uptime",
        "rx_packet_total",
        "mqtt_success_count",
        "mqtt_fail_count",
        "station_packet_age",
        "activity_state",
        "listen_frequency",
        "pairing_state",
        "ownership_status",
        "sd_status_reason",
        "observation_timestamp",
    }
    assert all(
        descriptions[key].entity_registry_enabled_default is False for key in disabled
    )
    assert descriptions["sd_capacity"].entity_registry_enabled_default is True
    assert descriptions["sd_filesystem"].entity_registry_enabled_default is True
    assert descriptions["gateway_uptime"].state_class is None
    assert descriptions["rx_packet_total"].state_class is None
    assert descriptions["mqtt_success_count"].state_class is None
    assert descriptions["mqtt_fail_count"].state_class is None
    assert descriptions["station_packet_age"].state_class is None
    # Firmware counters can restart with the gateway; never publish them as
    # monotonic totals that HA would interpret as resettable utility meters.


def test_status_diagnostics_preserve_uptime_and_select_paired_station() -> None:
    """Expose raw seconds and choose RSSI/SNR/age by paired station ID."""
    descriptions = {item.key: item for item in DIAGNOSTIC_SENSORS}
    info = {
        "uptime_sec": 987.625,
        "station": {"paired_id": 23},
    }
    status = {
        "uptime_sec": 1000,
        "recent_stations": [
            {"id": 24, "rssi": -90, "snr": -10, "age_sec": 2},
            {"id": 23, "rssi": -70, "snr": -4, "age_sec": 45},
        ],
    }
    assert (
        diagnostic_native_value(descriptions["gateway_uptime"], info, status) == 987.625
    )
    assert diagnostic_native_value(descriptions["station_rssi"], info, status) == -70
    assert diagnostic_native_value(descriptions["station_snr"], info, status) == -4
    assert (
        diagnostic_native_value(descriptions["station_packet_age"], info, status) == 45
    )
    assert (
        diagnostic_native_value(descriptions["station_rssi"], {"station": {}}, status)
        is None
    )


def test_sd_capacity_is_unavailable_when_card_is_missing_or_invalid() -> None:
    """Never turn an absent card's zero capacity into a healthy reading."""
    description = next(item for item in DIAGNOSTIC_SENSORS if item.key == "sd_capacity")
    assert diagnostic_native_value(description, {}, {"sd_capacity_gb": 16.0}) == 16.0
    assert (
        diagnostic_native_value(
            description, {}, {"sd_capacity_gb": 0, "sd_present": True}
        )
        is None
    )
    assert (
        diagnostic_native_value(
            description, {}, {"sd_capacity_gb": 16.0, "sd_present": False}
        )
        is None
    )


def test_connectivity_states_are_stable_for_known_and_unknown_values() -> None:
    """Distinguish known disconnected states from malformed or new values."""
    assert binary_sensor_value("wifi_connected", {"wifi": {"status": "CONNECTED"}}, {})
    assert binary_sensor_value(
        "wifi_connected", {"wifi": {"status": "CONNECTED_NO_INTERNET"}}, {}
    )
    for state in (
        "CONNECTING",
        "CONNECTED_NO_IP",
        "CONNECTION_FAILED",
        "DISCONNECTING",
        "DISCONNECTED",
    ):
        assert binary_sensor_value(
            "wifi_connected", {"wifi": {"status": state}}, {}
        ) is (state == "CONNECTED_NO_IP")
    assert (
        binary_sensor_value("wifi_connected", {"wifi": {"status": "future"}}, {})
        is None
    )
    assert binary_sensor_value("wifi_connected", {"wifi": {"status": 1}}, {}) is None
    assert binary_sensor_value("mqtt_connected", {}, {"mqtt_status": "CONNECTED"})
    assert (
        binary_sensor_value("mqtt_connected", {}, {"mqtt_status": "CONNECTION_FAILED"})
        is False
    )
    assert (
        binary_sensor_value("mqtt_connected", {}, {"mqtt_status": "DISCONNECTING"})
        is False
    )
    assert (
        binary_sensor_value("mqtt_connected", {}, {"mqtt_status": "unexpected"}) is None
    )
    assert binary_sensor_value("uplink_active", {}, {"uplink_active": "yes"}) is None


def test_operational_binary_sensor_availability_requires_source_fields() -> None:
    """Missing endpoint fields do not create entities with invented states."""
    assert not binary_sensor_available("sd_present", {}, {})
    assert binary_sensor_available("sd_present", {}, {"sd_present": False})
    assert binary_sensor_value("sd_present", {}, {"sd_present": False}) is False
    assert binary_sensor_value("sd_mounted", {}, {"sd_mounted": True}) is True
    assert binary_sensor_value("sd_unusable", {}, {"sd_unusable": True}) is True
    assert binary_sensor_available(
        "mqtt_connected", {}, {"mqtt_status": "DISCONNECTED"}
    )
    assert binary_sensor_available("station_paired", {}, {"is_paired": False})


@pytest.mark.parametrize(
    ("host", "port", "expected"),
    [
        ("gateway.local", 80, "http://gateway.local:80/"),
        ("192.0.2.18", 8080, "http://192.0.2.18:8080/"),
        ("2001:db8::5", 8123, "http://[2001:db8::5]:8123/"),
    ],
)
def test_configuration_url_uses_configured_hostname_and_port(
    host: str, port: int, expected: str
) -> None:
    """Support hostnames, IPv4, IPv6, and nonstandard local HTTP ports."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="GATEWAY-CONFIG-URL",
        data={"host": host, "port": port},
    )
    assert configuration_url(entry, {"wifi": {"ip": "192.0.2.44"}}) == expected


def test_configuration_url_fallback_and_device_metadata_validation() -> None:
    """Use reported IP only if configured host is invalid and validate MAC data."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="SANITIZED-GATEWAY-ID",
        data={"host": "bad host", "port": 8123},
    )
    info = {
        "gateway_id": "SANITIZED-GATEWAY-ID",
        "device_name": "Sanitized Gateway",
        "model": "WXM-WG1200",
        "hardware": "WXM-WG1200",
        "firmware": "0.8.39",
        "mac": "02:11:22:33:44:55",
        "wifi": {"ip": "192.0.2.44"},
    }
    device = device_info(entry, info)
    assert device["configuration_url"] == "http://192.0.2.44:8123/"
    assert device["name"] == "Sanitized Gateway"
    assert device["manufacturer"] == "WeatherXM"
    assert device["model"] == "WXM-WG1200"
    assert device["model_id"] == "WXM-WG1200"
    assert device.get("hw_version") is None
    assert device["serial_number"] == "SANITIZED-GATEWAY-ID"
    assert device["connections"] == {("mac", "02:11:22:33:44:55")}

    invalid = device_info(
        entry,
        {
            "gateway_id": "SANITIZED-GATEWAY-ID",
            "mac": "not-a-mac",
            "wifi": {"ip": "http://unsafe"},
        },
    )
    assert "configuration_url" not in invalid
    assert "connections" not in invalid
    assert invalid["identifiers"] == {(DOMAIN, "SANITIZED-GATEWAY-ID")}
