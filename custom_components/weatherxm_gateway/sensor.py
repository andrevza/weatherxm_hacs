"""Weather and diagnostic sensors."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    DEGREE,
    PERCENTAGE,
    UV_INDEX,
    EntityCategory,
    UnitOfFrequency,
    UnitOfInformation,
    UnitOfIrradiance,
    UnitOfPrecipitationDepth,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
    UnitOfTime,
    UnitOfVolumetricFlux,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import GatewayConfigEntry
from .api import observation_value
from .entity import DiagnosticCoordinatorEntity, WeatherCoordinatorEntity


@dataclass(frozen=True, kw_only=True)
class WeatherSensorDescription(SensorEntityDescription):
    """Weather field description."""

    field: str


WEATHER_SENSORS = (
    WeatherSensorDescription(
        key="temperature",
        translation_key="temperature",
        field="temp",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WeatherSensorDescription(
        key="feels_like",
        translation_key="feels_like",
        field="feels_like",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WeatherSensorDescription(
        key="humidity",
        translation_key="humidity",
        field="humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WeatherSensorDescription(
        key="pressure",
        translation_key="pressure",
        field="pressure",
        device_class=SensorDeviceClass.PRESSURE,
        native_unit_of_measurement=UnitOfPressure.HPA,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WeatherSensorDescription(
        key="wind_speed",
        translation_key="wind_speed",
        field="wind_speed",
        device_class=SensorDeviceClass.WIND_SPEED,
        native_unit_of_measurement=UnitOfSpeed.METERS_PER_SECOND,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WeatherSensorDescription(
        key="wind_gust",
        translation_key="wind_gust",
        field="wind_gust",
        device_class=SensorDeviceClass.WIND_SPEED,
        native_unit_of_measurement=UnitOfSpeed.METERS_PER_SECOND,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WeatherSensorDescription(
        key="wind_direction",
        translation_key="wind_direction",
        field="wind_dir_deg",
        device_class=SensorDeviceClass.WIND_DIRECTION,
        native_unit_of_measurement=DEGREE,
        state_class=SensorStateClass.MEASUREMENT_ANGLE,
    ),
    WeatherSensorDescription(
        key="rainfall_rate",
        translation_key="rainfall_rate",
        field="precip_rate",
        device_class=SensorDeviceClass.PRECIPITATION_INTENSITY,
        native_unit_of_measurement=UnitOfVolumetricFlux.MILLIMETERS_PER_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WeatherSensorDescription(
        key="daily_rainfall",
        translation_key="daily_rainfall",
        field="precip_daily",
        device_class=SensorDeviceClass.PRECIPITATION,
        native_unit_of_measurement=UnitOfPrecipitationDepth.MILLIMETERS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WeatherSensorDescription(
        key="rolling_rainfall",
        translation_key="rolling_rainfall",
        field="precip_24h",
        device_class=SensorDeviceClass.PRECIPITATION,
        native_unit_of_measurement=UnitOfPrecipitationDepth.MILLIMETERS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WeatherSensorDescription(
        key="lifetime_rainfall",
        translation_key="lifetime_rainfall",
        field="precip_cml",
        device_class=SensorDeviceClass.PRECIPITATION,
        native_unit_of_measurement=UnitOfPrecipitationDepth.MILLIMETERS,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    WeatherSensorDescription(
        key="uv_index",
        translation_key="uv_index",
        field="uv",
        native_unit_of_measurement=UV_INDEX,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WeatherSensorDescription(
        key="solar_irradiance",
        translation_key="solar_irradiance",
        field="irradiance",
        device_class=SensorDeviceClass.IRRADIANCE,
        native_unit_of_measurement=UnitOfIrradiance.WATTS_PER_SQUARE_METER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
)


@dataclass(frozen=True, kw_only=True)
class DiagnosticDescription(SensorEntityDescription):
    """Diagnostic field description."""

    field: str
    source: str = "info"


def _finite_numeric(value: Any) -> bool:
    """Check untrusted numeric API values without overflowing on huge integers."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


DIAGNOSTIC_SENSORS = (
    DiagnosticDescription(
        key="packet_reception",
        translation_key="packet_reception",
        field="packet_reception",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    DiagnosticDescription(
        key="wifi_rssi",
        translation_key="wifi_rssi",
        field="rssi",
        source="wifi",
        native_unit_of_measurement="dBm",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    DiagnosticDescription(
        key="wifi_state", translation_key="wifi_state", field="status", source="wifi"
    ),
    DiagnosticDescription(
        key="firmware_version", translation_key="firmware_version", field="firmware"
    ),
    DiagnosticDescription(
        key="api_version", translation_key="api_version", field="api_version"
    ),
    DiagnosticDescription(
        key="station_type",
        translation_key="station_type",
        field="station_type",
        source="station",
    ),
    DiagnosticDescription(
        key="station_firmware",
        translation_key="station_firmware",
        field="station_fw_version",
        source="station",
    ),
    DiagnosticDescription(
        key="paired_station_id",
        translation_key="paired_station_id",
        field="paired_id",
        source="station",
    ),
    DiagnosticDescription(
        key="station_rssi",
        translation_key="station_rssi",
        field="rssi",
        source="recent_station",
        native_unit_of_measurement="dBm",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    DiagnosticDescription(
        key="station_snr",
        translation_key="station_snr",
        field="snr",
        source="recent_station",
        native_unit_of_measurement="dB",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    DiagnosticDescription(
        key="mqtt_success_count",
        translation_key="mqtt_success_count",
        field="mqtt_success_count",
        source="status",
        native_unit_of_measurement="publishes",
        entity_registry_enabled_default=False,
    ),
    DiagnosticDescription(
        key="mqtt_fail_count",
        translation_key="mqtt_fail_count",
        field="mqtt_fail_count",
        source="status",
        native_unit_of_measurement="publishes",
        entity_registry_enabled_default=False,
    ),
    DiagnosticDescription(
        key="gateway_uptime",
        translation_key="gateway_uptime",
        field="uptime_sec",
        source="uptime",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        entity_registry_enabled_default=False,
    ),
    DiagnosticDescription(
        key="rx_packet_total",
        translation_key="rx_packet_total",
        field="rx_packet_total",
        source="status",
        native_unit_of_measurement="packets",
        entity_registry_enabled_default=False,
    ),
    DiagnosticDescription(
        key="station_packet_age",
        translation_key="station_packet_age",
        field="age_sec",
        source="recent_station",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        entity_registry_enabled_default=False,
    ),
    DiagnosticDescription(
        key="activity_state",
        translation_key="activity_state",
        field="activity_status",
        source="status",
        entity_registry_enabled_default=False,
    ),
    DiagnosticDescription(
        key="listen_frequency",
        translation_key="listen_frequency",
        field="listen_freq_hz",
        source="status",
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        entity_registry_enabled_default=False,
    ),
    DiagnosticDescription(
        key="pairing_state",
        translation_key="pairing_state",
        field="pairing_state",
        source="status",
        entity_registry_enabled_default=False,
    ),
    DiagnosticDescription(
        key="ownership_status",
        translation_key="ownership_status",
        field="ownership_status",
        source="status",
        entity_registry_enabled_default=False,
    ),
    DiagnosticDescription(
        key="sd_capacity",
        translation_key="sd_capacity",
        field="sd_capacity_gb",
        source="status",
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.GIGABYTES,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    DiagnosticDescription(
        key="sd_filesystem",
        translation_key="sd_filesystem",
        field="sd_fs_type",
        source="status",
    ),
    DiagnosticDescription(
        key="sd_status_reason",
        translation_key="sd_status_reason",
        field="sd_status_reason",
        source="status",
        entity_registry_enabled_default=False,
    ),
    DiagnosticDescription(
        key="observation_timestamp",
        translation_key="observation_timestamp",
        field="timestamp",
        source="observations",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_registry_enabled_default=False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GatewayConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up weather and supported diagnostic sensors."""
    runtime = entry.runtime_data
    entities: list[SensorEntity] = [
        WeatherSensor(runtime.weather, entry, description)
        for description in WEATHER_SENSORS
    ]
    for description in DIAGNOSTIC_SENSORS:
        if _diagnostic_available(runtime.diagnostics.data, description):
            entities.append(
                DiagnosticSensor(
                    runtime.diagnostics, entry, description, runtime.weather
                )
            )
    async_add_entities(entities)


def _diagnostic_available(
    data: dict[str, Any] | None, description: DiagnosticDescription
) -> bool:
    """Only create a diagnostic entity when the endpoint exposes its field."""
    if not data:
        return False
    info = data.get("info", {})
    status = data.get("status", {})
    if not isinstance(info, dict) or not isinstance(status, dict):
        return False
    if description.source == "info":
        if description.key == "packet_reception":
            station = info.get("station")
            return (
                isinstance(station, dict) and "packet_reception" in station
            ) or "packet_reception" in status
        if description.key == "firmware_version":
            return "firmware" in info or "fw_version" in info or "fw_version" in status
        return description.field in info
    if description.source == "wifi":
        return (
            description.field in info.get("wifi", {})
            or f"wifi_{description.field}" in status
        )
    if description.source == "station":
        return (
            description.field in info.get("station", {}) or description.field in status
        )
    if description.source == "recent_station":
        return description.field in _paired_station(info, status)
    if description.source == "status":
        return description.field in status
    if description.source == "uptime":
        return description.field in info or description.field in status
    if description.source == "observations":
        return True
    return False


def _paired_station(info: dict[str, Any], status: dict[str, Any]) -> dict[str, Any]:
    """Return recent data for the paired station, never an arbitrary station."""
    station = info.get("station") if isinstance(info.get("station"), dict) else {}
    paired_id = station.get("paired_id", status.get("paired_id"))
    if paired_id is None:
        return {}
    recent = status.get("recent_stations")
    if not isinstance(recent, list):
        return {}
    return next(
        (
            item
            for item in recent
            if isinstance(item, dict) and str(item.get("id")) == str(paired_id)
        ),
        {},
    )


def diagnostic_available(
    data: dict[str, Any] | None, description: DiagnosticDescription
) -> bool:
    """Public wrapper for availability checks used by entities and offline tools."""
    return _diagnostic_available(data, description)


class WeatherSensor(WeatherCoordinatorEntity, SensorEntity):
    """Sensor for a weather observation field."""

    entity_description: WeatherSensorDescription

    def __init__(
        self,
        coordinator,
        entry: GatewayConfigEntry,
        description: WeatherSensorDescription,
    ) -> None:
        super().__init__(coordinator, entry)
        self.entity_description = description
        self._attr_unique_id = f"{entry.unique_id}_{description.key}"

    @property
    def native_value(self) -> float | None:
        """Return a value only for a current valid observation."""
        return observation_value(self.coordinator.data, self.entity_description.field)


class DiagnosticSensor(DiagnosticCoordinatorEntity, SensorEntity):
    """Sensor for gateway or paired station diagnostics."""

    entity_description: DiagnosticDescription

    def __init__(
        self,
        coordinator,
        entry: GatewayConfigEntry,
        description: DiagnosticDescription,
        weather_coordinator=None,
    ) -> None:
        super().__init__(coordinator, entry)
        self.entity_description = description
        self._attr_unique_id = f"{entry.unique_id}_{description.key}"
        self._weather_coordinator = weather_coordinator
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def native_value(self) -> Any:
        """Resolve diagnostic values from documented response paths."""
        return diagnostic_native_value(
            self.entity_description,
            self.info,
            self.status,
            self._weather_coordinator.data if self._weather_coordinator else None,
        )


def diagnostic_native_value(
    description: DiagnosticDescription,
    info: dict[str, Any],
    status: dict[str, Any],
    observations: dict[str, Any] | None = None,
) -> Any:
    """Shared pure diagnostic extraction used by entities and capture validator."""
    station = info.get("station") if isinstance(info.get("station"), dict) else {}
    wifi = info.get("wifi") if isinstance(info.get("wifi"), dict) else {}
    desc = description
    value: Any = None
    if desc.source == "info":
        if desc.key == "packet_reception":
            value = station.get("packet_reception", status.get("packet_reception"))
        elif desc.key == "firmware_version":
            value = info.get(
                "firmware", info.get("fw_version", status.get("fw_version"))
            )
        else:
            value = info.get(desc.field)
    elif desc.source == "wifi":
        value = wifi.get(desc.field, status.get(f"wifi_{desc.field}"))
    elif desc.source == "station":
        fallback = (
            "station_fw_ver" if desc.field == "station_fw_version" else desc.field
        )
        value = station.get(desc.field, status.get(fallback))
    elif desc.source == "recent_station":
        value = _paired_station(info, status).get(desc.field)
    elif desc.source == "status":
        value = status.get(desc.field)
    elif desc.source == "uptime":
        value = info.get(desc.field, status.get(desc.field))
    elif desc.source == "observations":
        timestamp = (observations or {}).get("timestamp")
        return (
            datetime.fromtimestamp(timestamp, tz=UTC)
            if isinstance(timestamp, (int, float)) and not isinstance(timestamp, bool)
            else None
        )
    if desc.key == "sd_capacity":
        if status.get("sd_present") is False:
            return None
        if not _finite_numeric(value) or value <= 0:
            return None
    if desc.key in {
        "gateway_uptime",
        "rx_packet_total",
        "mqtt_success_count",
        "mqtt_fail_count",
        "station_packet_age",
        "listen_frequency",
    }:
        if not _finite_numeric(value) or value < 0:
            return None
    if desc.state_class == SensorStateClass.MEASUREMENT:
        if not _finite_numeric(value):
            return None
    if isinstance(value, str) and (not value.strip() or len(value) > 128):
        return None
    return value
