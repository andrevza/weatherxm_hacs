"""Coordinators for WeatherXM gateway weather and diagnostics."""

from __future__ import annotations

import logging
import time
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    GatewayApi,
    GatewayConnectionError,
    GatewayError,
    observation_is_current,
)
from .const import (
    CONF_DIAGNOSTIC_INTERVAL,
    CONF_SCAN_INTERVAL,
    DEFAULT_DIAGNOSTIC_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class WeatherCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Poll current observation data."""

    def __init__(
        self, hass: HomeAssistant, api: GatewayApi, entry: ConfigEntry
    ) -> None:
        self.api = api
        self.entry = entry
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} weather {entry.unique_id}",
            update_interval=timedelta(
                seconds=entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
            ),
        )

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            data = await self.api.async_get_observations()
        except GatewayError as err:
            raise UpdateFailed("Unable to update WeatherXM weather data") from err
        data["has_weather"] = observation_is_current(
            data,
            now=time.time(),
            max_age=max(180, self.update_interval.total_seconds() * 3),
        )
        return data


class DiagnosticCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Poll gateway diagnostics independently from weather data."""

    def __init__(
        self, hass: HomeAssistant, api: GatewayApi, entry: ConfigEntry
    ) -> None:
        self.api = api
        self.entry = entry
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} diagnostics {entry.unique_id}",
            update_interval=timedelta(
                seconds=entry.options.get(
                    CONF_DIAGNOSTIC_INTERVAL, DEFAULT_DIAGNOSTIC_INTERVAL
                )
            ),
        )

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            info, status = (
                await self.api.async_get_info(),
                await self.api.async_get_status(),
            )
        except GatewayConnectionError as err:
            raise UpdateFailed(
                "Unable to update WeatherXM gateway diagnostics"
            ) from err
        except GatewayError as err:
            raise UpdateFailed("Invalid WeatherXM gateway diagnostics") from err
        return {"info": info, "status": status}
