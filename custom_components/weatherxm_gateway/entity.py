"""Shared entities for WeatherXM gateway."""

from __future__ import annotations

import re

from homeassistant.const import CONF_HOST
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import GatewayConfigEntry
from .api import gateway_id, validate_host
from .const import CONF_PORT, DEFAULT_PORT, DOMAIN

_MAC_RE = re.compile(r"^(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}$")


def configuration_url(entry: GatewayConfigEntry, info: dict) -> str | None:
    """Build a safe URL for the gateway's local web interface."""
    host = entry.data.get(CONF_HOST)
    port = entry.data.get(CONF_PORT, DEFAULT_PORT)
    try:
        host = validate_host(host) if isinstance(host, str) else None
    except ValueError:
        host = None
    if host is None:
        wifi = info.get("wifi") if isinstance(info.get("wifi"), dict) else {}
        reported_ip = wifi.get("ip")
        try:
            host = validate_host(reported_ip) if isinstance(reported_ip, str) else None
        except ValueError:
            host = None
    if host is None:
        return None
    if isinstance(port, bool) or not isinstance(port, int) or not 1 <= port <= 65535:
        port = DEFAULT_PORT
    url_host = f"[{host}]" if ":" in host else host
    return f"http://{url_host}:{port}/"


def device_info(entry: GatewayConfigEntry, info: dict) -> DeviceInfo:
    """Return the gateway's stable device registry identity."""
    hardware = info.get("hardware")
    model = info.get("model")
    firmware = info.get("firmware", info.get("fw_version"))
    raw_mac = info.get("mac")
    connections: set[tuple[str, str]] = set()
    if isinstance(raw_mac, str) and _MAC_RE.fullmatch(raw_mac):
        connections.add((dr.CONNECTION_NETWORK_MAC, raw_mac.replace("-", ":").lower()))

    def text(value: object, fallback: str | None = None) -> str | None:
        if not isinstance(value, str):
            return fallback
        value = value.strip()
        return (
            value if value and len(value) <= 128 and value.isprintable() else fallback
        )

    details: DeviceInfo = {
        "identifiers": {(DOMAIN, entry.unique_id)},
        "name": text(info.get("device_name"), "WeatherXM Gateway"),
        "manufacturer": "WeatherXM",
        "model": text(model, text(hardware, "WG1200")),
    }
    if connections:
        details["connections"] = connections
    if url := configuration_url(entry, info):
        details["configuration_url"] = url
    if model_id := text(hardware):
        details["model_id"] = model_id
    if serial := gateway_id(info):
        details["serial_number"] = serial
    if sw_version := text(firmware):
        details["sw_version"] = sw_version
    return details


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
