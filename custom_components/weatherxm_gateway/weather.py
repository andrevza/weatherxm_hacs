"""Native Home Assistant weather entity for measured conditions."""

from __future__ import annotations

import math
from typing import Any

from homeassistant.components.weather import WeatherEntity
from homeassistant.const import UnitOfPressure, UnitOfSpeed, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import GatewayConfigEntry
from .api import observation_value
from .const import CONF_ESTIMATE_CONDITION
from .entity import device_info


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GatewayConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up measured-conditions entity."""
    async_add_entities([GatewayWeather(entry)])


class GatewayWeather(CoordinatorEntity, WeatherEntity):
    """Weather entity with measured conditions and optional estimates."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_translation_key = "current"
    _attr_native_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_native_pressure_unit = UnitOfPressure.HPA
    _attr_native_wind_speed_unit = UnitOfSpeed.METERS_PER_SECOND

    def __init__(self, entry: GatewayConfigEntry) -> None:
        super().__init__(entry.runtime_data.weather)
        self._entry = entry
        self._attr_unique_id = f"{entry.unique_id}_weather"
        data = entry.runtime_data.diagnostics.data or {}
        self._attr_device_info = device_info(entry, data.get("info", {}))

    @property
    def condition(self) -> str | None:
        """Return no condition by default or estimate one from local readings."""
        if not self._entry.options.get(CONF_ESTIMATE_CONDITION, False):
            return None
        return estimated_condition(self.coordinator.data)

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


def estimated_condition(data: dict[str, Any] | None) -> str | None:
    """Estimate only conditions supported by current precipitation/radiation data.

    The WG1200 does not report cloud cover. This intentionally never returns
    partly-cloudy or clear-night, and treats UV only as supporting evidence for
    strong irradiance rather than as proof of sunshine by itself.
    """
    if not data or data.get("has_weather") is not True:
        return None

    rain = observation_value(data, "precip_rate")
    wind = observation_value(data, "wind_speed")
    irradiance = observation_value(data, "irradiance")
    uv_index = observation_value(data, "uv")

    if rain is not None and math.isfinite(rain):
        if rain >= 7.5:
            return "pouring"
        if rain > 0:
            return "rainy"
    if wind is not None and math.isfinite(wind) and wind >= 40 / 3.6:
        return "windy"
    if irradiance is not None and math.isfinite(irradiance):
        if irradiance >= 500 or (
            irradiance >= 300
            and uv_index is not None
            and math.isfinite(uv_index)
            and uv_index >= 6
        ):
            return "sunny"
    return None
