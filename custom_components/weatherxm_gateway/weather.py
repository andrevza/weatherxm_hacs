"""Native Home Assistant weather entity for measured conditions."""

from __future__ import annotations

from homeassistant.components.weather import WeatherEntity
from homeassistant.const import UnitOfPressure, UnitOfSpeed, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import GatewayConfigEntry
from .api import observation_value
from .entity import device_info


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GatewayConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up measured-conditions entity."""
    async_add_entities([GatewayWeather(entry)])


class GatewayWeather(CoordinatorEntity, WeatherEntity):
    """Weather entity with observed conditions and no forecast or inferred state."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_translation_key = "current"
    _attr_native_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_native_pressure_unit = UnitOfPressure.HPA
    _attr_native_wind_speed_unit = UnitOfSpeed.METERS_PER_SECOND

    def __init__(self, entry: GatewayConfigEntry) -> None:
        super().__init__(entry.runtime_data.weather)
        self._attr_unique_id = f"{entry.unique_id}_weather"
        data = entry.runtime_data.diagnostics.data or {}
        self._attr_device_info = device_info(entry, data.get("info", {}))

    @property
    def condition(self) -> None:
        """No dependable condition classification is provided by the gateway."""
        return None

    @property
    def native_temperature(self) -> float | None:
        """Observed air temperature."""
        return self._value("temp")

    @property
    def native_apparent_temperature(self) -> float | None:
        """Observed feels-like temperature."""
        return self._value("feels_like")

    @property
    def humidity(self) -> float | None:
        """Observed relative humidity."""
        return self._value("humidity")

    @property
    def native_pressure(self) -> float | None:
        """Observed atmospheric pressure."""
        return self._value("pressure")

    @property
    def native_wind_speed(self) -> float | None:
        """Observed wind speed."""
        return self._value("wind_speed")

    @property
    def native_wind_gust_speed(self) -> float | None:
        """Observed wind gust."""
        return self._value("wind_gust")

    @property
    def wind_bearing(self) -> float | None:
        """Observed bearing, preserving valid north (0 degrees)."""
        return self._value("wind_dir_deg")

    def _value(self, key: str) -> float | None:
        return observation_value(self.coordinator.data, key)
