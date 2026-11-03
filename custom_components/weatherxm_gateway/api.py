"""Async client for the read-only local WG1200 REST API."""

from __future__ import annotations

import ipaddress
import json
import logging
import re
from typing import Any

from aiohttp import ClientError, ClientSession, ClientTimeout

from .const import MAX_RESPONSE_BYTES, REQUEST_TIMEOUT

_LOGGER = logging.getLogger(__name__)
_HOST_RE = re.compile(r"^(?=.{1,253}$)[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?$")


class GatewayError(Exception):
    """Base API error."""


class GatewayConnectionError(GatewayError):
    """Connection, timeout, or HTTP error."""


class GatewayInvalidResponse(GatewayError):
    """Invalid or unexpectedly large response."""


def validate_host(host: str) -> str:
    """Validate an IP address or DNS name and return a normalized host."""
    value = host.strip().rstrip(".")
    if not value or any(char in value for char in "/\\@?#"):
        raise ValueError("Enter a hostname or IP address without a URL or port")
    try:
        return str(ipaddress.ip_address(value))
    except ValueError:
        if not _HOST_RE.fullmatch(value) or ".." in value:
            raise ValueError("Enter a valid hostname or IP address") from None
        return value


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _finite_number(value: Any) -> float | None:
    """Return a finite numeric value, rejecting booleans and malformed data."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        result = float(value)
    except OverflowError:
        return None
    return result if result == result and abs(result) != float("inf") else None


def _unit(payload: dict[str, Any], kind: str) -> str | None:
    units = _mapping(payload.get("units"))
    value = payload.get(f"unit_{kind}", units.get(kind))
    return value.strip() if isinstance(value, str) and value.strip() else None


def observation_units(
    data: Any, info: dict[str, Any] | None = None
) -> dict[str, str | None]:
    """Return the same effective API units used during observation conversion."""
    raw = _mapping(data)
    fallback_units = _mapping(_mapping(info).get("units"))
    merged_units = dict(raw.get("units")) if isinstance(raw.get("units"), dict) else {}
    for key in ("temp", "wind", "precip", "press"):
        if not merged_units.get(key):
            merged_units[key] = fallback_units.get(key)
    source = dict(raw)
    source["units"] = merged_units
    return {key: _unit(source, key) for key in ("temp", "wind", "precip", "press")}


def observation_value(data: dict[str, Any] | None, field: str) -> float | None:
    """Return an entity-ready weather value only for reported weather data."""
    if not data or data.get("has_weather") is not True:
        return None
    value = data.get(field)
    return (
        float(value)
        if isinstance(value, (int, float)) and not isinstance(value, bool)
        else None
    )


def _convert(value: Any, kind: str, unit: str | None) -> float | None:
    """Convert recognized API units to Home Assistant canonical native units."""
    number = _finite_number(value)
    if number is None:
        return None
    if unit is None:
        return None
    normalized = unit.lower().replace(" ", "")
    if kind == "temp":
        if normalized in ("°c", "c", "celsius"):
            return number
        if normalized in ("°f", "f", "fahrenheit"):
            return (number - 32) * 5 / 9
    elif kind == "wind":
        factors = {
            "m/s": 1,
            "mps": 1,
            "km/h": 1 / 3.6,
            "kph": 1 / 3.6,
            "mph": 0.44704,
            "kn": 0.514444,
            "knot": 0.514444,
            "knots": 0.514444,
        }
        if normalized in factors:
            return number * factors[normalized]
    elif kind == "precip":
        if normalized in ("mm", "mm/h", "millimeter", "millimeters"):
            return number
        if normalized in ("in", "inch", "inches", "in/h"):
            return number * 25.4
    elif kind == "press":
        factors = {
            "hpa": 1,
            "mbar": 1,
            "pa": 0.01,
            "kpa": 10,
            "inhg": 33.8638866667,
            "mmhg": 1.333223874,
        }
        if normalized in factors:
            return number * factors[normalized]
    elif kind == "angle" and normalized in ("°", "deg", "degree", "degrees", ""):
        return number
    elif kind == "percent" and normalized in ("%", "percent", ""):
        return number
    elif kind in ("uv", "irradiance"):
        return number
    return None


def _bounded(value: float | None, minimum: float, maximum: float) -> float | None:
    """Reject numerically valid but physically implausible measurements."""
    return value if value is not None and minimum <= value <= maximum else None


def normalize_observations(
    data: Any, info: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Validate fields and convert measurements to canonical units."""
    raw = _mapping(data)
    info = info or {}
    units = observation_units(raw, info)
    source = dict(raw)
    source["units"] = units
    for key in ("temp", "feels_like"):
        source[key] = _convert(raw.get(key), "temp", units["temp"])
    for key in ("wind_speed", "wind_gust"):
        source[key] = _convert(raw.get(key), "wind", units["wind"])
    for key in ("precip_rate", "precip_daily", "precip_cml", "precip_24h"):
        source[key] = _convert(raw.get(key), "precip", units["precip"])
    source["pressure"] = _convert(raw.get("pressure"), "press", units["press"])
    source["wind_dir_deg"] = _convert(raw.get("wind_dir_deg"), "angle", "°")
    source["humidity"] = _convert(raw.get("humidity"), "percent", "%")
    source["uv"] = _convert(raw.get("uv"), "uv", "")
    source["irradiance"] = _convert(raw.get("irradiance"), "irradiance", "")
    for key in ("temp", "feels_like"):
        source[key] = _bounded(source[key], -90, 70)
    source["humidity"] = _bounded(source["humidity"], 0, 100)
    source["pressure"] = _bounded(source["pressure"], 250, 1200)
    for key in ("wind_speed", "wind_gust"):
        source[key] = _bounded(source[key], 0, 200)
    source["wind_dir_deg"] = _bounded(source["wind_dir_deg"], 0, 360)
    for key in (
        "precip_rate",
        "precip_daily",
        "precip_cml",
        "precip_24h",
        "uv",
        "irradiance",
    ):
        source[key] = _bounded(source[key], 0, float("inf"))
    source["has_weather"] = raw.get("has_weather") is True
    timestamp = raw.get("timestamp")
    source["timestamp"] = (
        int(timestamp)
        if isinstance(timestamp, (int, float))
        and not isinstance(timestamp, bool)
        and 0 < timestamp <= 4_102_444_800
        else None
    )
    return source


def observation_is_current(data: dict[str, Any], *, now: float, max_age: float) -> bool:
    """Apply the same timestamp and weather-presence policy used by entities."""
    return observation_freshness(data, now=now, max_age=max_age) == "current"


def observation_freshness(data: dict[str, Any], *, now: float, max_age: float) -> str:
    """Explain why an observation is current or unavailable to weather entities."""
    if data.get("has_weather") is not True:
        return "no weather reported"
    timestamp = data.get("timestamp")
    if not isinstance(timestamp, (int, float)) or isinstance(timestamp, bool):
        return "timestamp missing or invalid"
    if timestamp > now + 300:
        return "timestamp is in the future"
    if now - timestamp > max_age:
        return "observation is stale"
    return "current"


class GatewayApi:
    """Bounded, read-only client using Home Assistant's shared session."""

    def __init__(self, host: str, port: int, session: ClientSession) -> None:
        self.host = validate_host(host)
        if (
            isinstance(port, bool)
            or not isinstance(port, int)
            or not 1 <= port <= 65535
        ):
            raise ValueError("Port must be between 1 and 65535")
        self.port = port
        self._session = session
        url_host = f"[{self.host}]" if ":" in self.host else self.host
        self._base_url = f"http://{url_host}:{port}"

    async def get_json(self, path: str) -> dict[str, Any]:
        """Fetch one JSON object without following redirects."""
        try:
            async with self._session.get(
                f"{self._base_url}{path}",
                timeout=ClientTimeout(total=REQUEST_TIMEOUT),
                allow_redirects=False,
            ) as response:
                if response.status < 200 or response.status >= 300:
                    raise GatewayConnectionError(
                        f"Gateway returned HTTP {response.status}"
                    )
                if (
                    response.content_length is not None
                    and response.content_length > MAX_RESPONSE_BYTES
                ):
                    raise GatewayInvalidResponse("Response exceeds the size limit")
                body = bytearray()
                async for chunk in response.content.iter_chunked(8192):
                    body.extend(chunk)
                    if len(body) > MAX_RESPONSE_BYTES:
                        raise GatewayInvalidResponse("Response exceeds the size limit")
                try:
                    result = json.loads(body)
                except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as err:
                    raise GatewayInvalidResponse(
                        "Gateway returned invalid JSON"
                    ) from err
                if not isinstance(result, dict):
                    raise GatewayInvalidResponse(
                        "Gateway response was not a JSON object"
                    )
                return result
        except (TimeoutError, ClientError) as err:
            _LOGGER.debug(
                "Unable to reach WeatherXM gateway at %s:%s", self.host, self.port
            )
            raise GatewayConnectionError("Unable to reach gateway") from err

    async def async_get_info(self) -> dict[str, Any]:
        """Fetch gateway information."""
        return normalize_info(await self.get_json("/api/v1/info"))

    async def async_get_observations(
        self, info: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Fetch current observations and normalize them."""
        return normalize_observations(await self.get_json("/api/v1/observations"), info)

    async def async_get_status(self) -> dict[str, Any]:
        """Fetch diagnostics."""
        return normalize_status(await self.get_json("/status"))

    async def async_get_history(self) -> dict[str, Any]:
        """Fetch history for future use; no Recorder imports are performed."""
        return await self.get_json("/api/v1/history")


def gateway_id(info: dict[str, Any]) -> str | None:
    """Get the stable hardware identifier, never the paired station id."""
    for candidate in (info.get("gateway_id"), info.get("id")):
        if (
            isinstance(candidate, str)
            and candidate.strip()
            and len(candidate.strip()) <= 128
        ):
            value = candidate.strip()
            if all(char.isprintable() for char in value):
                return value
    return None


def info_model(info: dict[str, Any]) -> str | None:
    """Read model from firmware variants."""
    for key in ("model", "hardware"):
        value = info.get(key)
        if isinstance(value, str) and value.strip() and len(value.strip()) <= 128:
            return value.strip()
    return None


def supported_model(value: str | None) -> bool:
    """Accept production and development/edition WG1200 hardware identifiers."""
    return value == "WXM-WG1200" or bool(value and value.startswith("WXM-WG1200-"))


def normalize_info(data: Any) -> dict[str, Any]:
    """Keep documented nested info objects from malformed payloads safe."""
    result = dict(_mapping(data))
    for key in ("wifi", "station", "units"):
        if not isinstance(result.get(key), dict):
            result[key] = {}
    return result


def normalize_status(data: Any) -> dict[str, Any]:
    """Sanitize status fields consumed by entity implementations."""
    result = dict(_mapping(data))
    recent = result.get("recent_stations")
    result["recent_stations"] = (
        [item for item in recent if isinstance(item, dict)]
        if isinstance(recent, list)
        else []
    )
    return result
