"""Tests for measurement metadata and diagnostic field selection."""

from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass

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
