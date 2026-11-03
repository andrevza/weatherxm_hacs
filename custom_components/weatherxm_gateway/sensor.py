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
    UnitOfIrradiance,
    UnitOfPrecipitationDepth,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
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


DIAGNOSTIC_SENSORS = (
    DiagnosticDescription(
        key="packet_reception",
        translation_key="packet_reception",
        field="packet_reception",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=None,
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
    if description.source == "info":
        if description.key == "packet_reception":
            station = info.get("station", {})
            return (
                "packet_reception" in station
                or "reception" in station
                or "packet_reception" in status
            )
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
        return any(
            isinstance(item, dict) and description.field in item
            for item in status.get("recent_stations", [])
        )
    if description.source == "observations":
        return True
    return False


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
            value = station.get(
                "packet_reception",
                station.get("reception", status.get("packet_reception")),
            )
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
        paired = station.get("paired_id", status.get("paired_id"))
        recent = status.get("recent_stations", [])
        value = next(
            (
                item.get(desc.field)
                for item in (recent if isinstance(recent, list) else [])
                if isinstance(item, dict) and str(item.get("id")) == str(paired)
            ),
            None,
        )
    elif desc.source == "observations":
        timestamp = (observations or {}).get("timestamp")
        return (
            datetime.fromtimestamp(timestamp, tz=UTC)
            if isinstance(timestamp, (int, float)) and not isinstance(timestamp, bool)
            else None
        )
    if desc.state_class == SensorStateClass.MEASUREMENT:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        try:
            if not math.isfinite(value):
                return None
        except OverflowError:
            return None
    return value
