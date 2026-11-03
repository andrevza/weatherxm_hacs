"""Privacy-conscious diagnostics for a WeatherXM gateway config entry."""

from __future__ import annotations

import time
from datetime import datetime
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import (
    CONF_HOST,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_PASSWORD,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntry
from homeassistant.loader import async_get_integration

from . import GatewayConfigEntry
from .api import observation_freshness
from .const import (
    CONF_DIAGNOSTIC_INTERVAL,
    CONF_SCAN_INTERVAL,
    DEFAULT_DIAGNOSTIC_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)
from .sensor import _paired_station

TO_REDACT = {
    CONF_HOST,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_PASSWORD,
    CONF_USERNAME,
    "id",
    "gateway_id",
    "paired_id",
    "serial_number",
    "mac",
    "ip",
    "ssid",
    "device_name",
    "hostname",
    "public_key",
    "pubkey",
    "latitude",
    "longitude",
    "url",
}

INFO_FIELDS = (
    "model",
    "hardware",
    "firmware",
    "fw_version",
    "api_version",
    "uptime_sec",
    "edition",
    "freq_region",
)
STATION_FIELDS = (
    "is_paired",
    "station_type",
    "station_fw_version",
    "packet_reception",
    "pair_mode",
)
WIFI_FIELDS = ("status", "rssi")
STATUS_FIELDS = (
    "wifi_status",
    "wifi_rssi",
    "mqtt_status",
    "mqtt_success_count",
    "mqtt_fail_count",
    "activity_status",
    "active_link",
    "lora_link_ok",
    "uplink_enabled",
    "uplink_active",
    "uptime_sec",
    "packet_reception",
    "is_paired",
    "pairing_state",
    "ownership_status",
    "listen_freq_hz",
    "rx_packet_total",
    "sd_mounted",
    "sd_present",
    "sd_unusable",
    "sd_capacity_gb",
    "sd_fs_type",
    "sd_status_reason",
)
OBSERVATION_FIELDS = (
    "has_weather",
    "timestamp",
    "temp",
    "feels_like",
    "humidity",
    "pressure",
    "wind_speed",
    "wind_gust",
    "wind_dir_deg",
    "precip_rate",
    "precip_daily",
    "precip_24h",
    "precip_cml",
    "uv",
    "irradiance",
)
SD_STATUS_REASONS = {
    "mounted",
    "not_mounted",
    "not_present",
    "unavailable",
    "unusable",
    "mount_failed",
    "filesystem_error",
    "format_error",
    "io_error",
    "unknown",
}


def _present_missing(
    data: dict[str, Any], expected: tuple[str, ...]
) -> dict[str, list[str]]:
    """Report only known field names, never arbitrary API-provided keys."""
    present = sorted(field for field in expected if field in data)
    return {"present": present, "missing": sorted(set(expected) - set(present))}


def _safe_string(value: Any, *, maximum: int = 128) -> str | None:
    """Keep bounded printable API text for fields with stable enum meanings."""
    if not isinstance(value, str):
        return None
    value = value.strip()
    if not value or len(value) > maximum or not value.isprintable():
        return None
    return value


def _safe_reason(value: Any) -> str | None:
    """Return only static SD status codes, excluding arbitrary diagnostic text."""
    value = _safe_string(value, maximum=96)
    if value is None:
        return None
    normalized = value.lower().replace("-", "_").replace(" ", "_")
    return normalized if normalized in SD_STATUS_REASONS else None


def _safe_coordinator_status(coordinator: Any) -> dict[str, Any]:
    """Report polling health and the last successful update without raw data."""
    if coordinator is None:
        return {"available": False, "last_update_success": False}
    interval = getattr(coordinator, "update_interval", None)
    last_success = getattr(coordinator, "last_update_success_time", None)
    if isinstance(last_success, datetime):
        last_success = last_success.isoformat()
    else:
        last_success = None
    return {
        "available": True,
        "poll_interval_seconds": (
            interval.total_seconds() if interval is not None else None
        ),
        "last_update_success": bool(getattr(coordinator, "last_update_success", False)),
        "last_successful_update": last_success,
    }


def _safe_device_snapshot(
    info: dict[str, Any], status: dict[str, Any]
) -> dict[str, Any]:
    """Project verified values into a public-safe gateway diagnostics snapshot."""
    station = info.get("station") if isinstance(info.get("station"), dict) else {}
    wifi = info.get("wifi") if isinstance(info.get("wifi"), dict) else {}
    paired = _paired_station(info, status)

    gateway = {key: info[key] for key in INFO_FIELDS if key in info}
    gateway.update({key: status[key] for key in STATUS_FIELDS if key in status})
    gateway["wifi"] = {key: wifi[key] for key in WIFI_FIELDS if key in wifi}
    gateway["station"] = {key: station[key] for key in STATION_FIELDS if key in station}
    gateway["station_radio"] = {
        key: paired[key]
        for key in ("rssi", "snr", "age_sec", "channel_slot")
        if key in paired
    }
    if "sd_status_reason" in gateway:
        gateway["sd_status_reason"] = _safe_reason(gateway["sd_status_reason"])
    return async_redact_data(gateway, TO_REDACT)


async def _async_build_diagnostics(
    hass: HomeAssistant, entry: GatewayConfigEntry
) -> dict[str, Any]:
    """Create redacted diagnostics even when setup or polling has failed."""
    runtime = getattr(entry, "runtime_data", None)
    weather = getattr(runtime, "weather", None)
    diagnostics = getattr(runtime, "diagnostics", None)
    weather_data = getattr(weather, "data", None)
    diagnostic_data = getattr(diagnostics, "data", None)
    info = diagnostic_data.get("info", {}) if isinstance(diagnostic_data, dict) else {}
    status = (
        diagnostic_data.get("status", {}) if isinstance(diagnostic_data, dict) else {}
    )
    observations = weather_data if isinstance(weather_data, dict) else {}
    if not isinstance(info, dict):
        info = {}
    if not isinstance(status, dict):
        status = {}
    station = info.get("station") if isinstance(info.get("station"), dict) else {}
    wifi = info.get("wifi") if isinstance(info.get("wifi"), dict) else {}

    integration = await async_get_integration(hass, DOMAIN)
    options = entry.options
    weather_interval = options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    diagnostic_interval = options.get(
        CONF_DIAGNOSTIC_INTERVAL, DEFAULT_DIAGNOSTIC_INTERVAL
    )
    return {
        "integration": {
            "domain": DOMAIN,
            "version": integration.version,
            "weather_poll_interval_seconds": weather_interval,
            "diagnostic_poll_interval_seconds": diagnostic_interval,
            "weather_api": _safe_coordinator_status(weather),
            "diagnostic_api": _safe_coordinator_status(diagnostics),
            "observation_freshness": (
                observation_freshness(
                    observations,
                    now=time.time(),
                    max_age=max(180, weather_interval * 3),
                )
                if observations
                else "unavailable"
            ),
        },
        "config_entry": async_redact_data(
            {"data": entry.data, "options": entry.options}, TO_REDACT
        ),
        "device": _safe_device_snapshot(info, status),
        "available_fields": {
            "info": {
                "gateway": _present_missing(info, INFO_FIELDS),
                "station": _present_missing(station, STATION_FIELDS),
                "wifi": _present_missing(wifi, WIFI_FIELDS),
            },
            "status": _present_missing(status, STATUS_FIELDS),
            "observations": _present_missing(observations, OBSERVATION_FIELDS),
        },
        "observations": {
            key: observations[key] for key in OBSERVATION_FIELDS if key in observations
        },
    }


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: GatewayConfigEntry
) -> dict[str, Any]:
    """Return redacted diagnostics for this gateway config entry."""
    return await _async_build_diagnostics(hass, entry)


async def async_get_device_diagnostics(
    hass: HomeAssistant, entry: GatewayConfigEntry, device: DeviceEntry
) -> dict[str, Any]:
    """Return diagnostics only when the device belongs to this gateway entry."""
    if (DOMAIN, entry.unique_id) not in device.identifiers:
        return {}
    return await _async_build_diagnostics(hass, entry)
