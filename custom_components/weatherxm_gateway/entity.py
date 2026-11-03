"""Shared entities for WeatherXM gateway."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import GatewayConfigEntry
from .const import DOMAIN


def device_info(entry: GatewayConfigEntry, info: dict) -> DeviceInfo:
    """Return the gateway's stable device registry identity."""
    return DeviceInfo(
        identifiers={(DOMAIN, entry.unique_id)},
        name=str(info.get("device_name") or "WeatherXM Gateway"),
        manufacturer="WeatherXM",
        model=str(info.get("model") or info.get("hardware") or "WG1200"),
        sw_version=str(info.get("firmware") or info.get("fw_version") or "") or None,
    )


class WeatherCoordinatorEntity(CoordinatorEntity):
    """Entity backed by current weather observations."""

    _attr_has_entity_name = True

    def __init__(self, coordinator, entry: GatewayConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        data = entry.runtime_data.diagnostics.data or {}
        self._attr_device_info = device_info(entry, data.get("info", {}))


class DiagnosticCoordinatorEntity(CoordinatorEntity):
    """Entity backed by gateway diagnostic payloads."""

    _attr_has_entity_name = True

    def __init__(self, coordinator, entry: GatewayConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        data = coordinator.data or {}
        self._attr_device_info = device_info(entry, data.get("info", {}))

    @property
    def info(self) -> dict:
        """Gateway information object."""
        data = self.coordinator.data or {}
        info = data.get("info")
        return info if isinstance(info, dict) else {}

    @property
    def status(self) -> dict:
        """Gateway status object."""
        data = self.coordinator.data or {}
        status = data.get("status")
        return status if isinstance(status, dict) else {}

    @property
    def station(self) -> dict:
        """Station information object."""
        station = self.info.get("station")
        return station if isinstance(station, dict) else {}
