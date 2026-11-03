"""Tests for WG1200 API parsing and unit normalization."""

from __future__ import annotations

import json
from typing import Any

import pytest

from custom_components.weatherxm_gateway.api import (
    GatewayApi,
    GatewayConnectionError,
    GatewayInvalidResponse,
    gateway_id,
    normalize_observations,
    observation_is_current,
    validate_host,
)


@pytest.mark.parametrize(
    ("direction", "expected"),
    [(0, 0), (151, 151), (359, 359), (None, None)],
)
def test_wind_direction_values(direction: int | None, expected: int | None) -> None:
    """Keep north valid and preserve valid angles without guessing."""
    observation = normalize_observations(
        {"has_weather": True, "wind_dir_deg": direction}
    )
    assert observation["wind_dir_deg"] == expected


@pytest.mark.parametrize("missing", [None, "absent"])
def test_wind_direction_missing_or_null(missing: None | str) -> None:
    """Missing and null directions stay unavailable."""
    payload: dict[str, Any] = {"has_weather": True}
    if missing is None:
        payload["wind_dir_deg"] = None
    assert normalize_observations(payload)["wind_dir_deg"] is None


def test_packet_reception_actual_and_documented_fields() -> None:
    """Both confirmed actual and older documented packet reception names parse."""
    for name in ("packet_reception", "reception"):
        station = {name: 94}
        assert station.get("packet_reception", station.get("reception")) == 94


def test_units_are_converted_from_reported_metadata() -> None:
    """Convert API units to canonical native units before entity exposure."""
    data = normalize_observations(
        {
            "has_weather": True,
            "temp": 68,
            "wind_speed": 36,
            "pressure": 101.325,
            "precip_daily": 0.5,
            "units": {"temp": "°F", "wind": "km/h", "press": "kPa", "precip": "in"},
        }
    )
    assert data["temp"] == pytest.approx(20)
    assert data["wind_speed"] == pytest.approx(10)
    assert data["pressure"] == pytest.approx(1013.25)
    assert data["precip_daily"] == pytest.approx(12.7)


def test_malformed_unit_metadata_makes_field_unavailable() -> None:
    """Never label unknown units as familiar ones."""
    data = normalize_observations(
        {"has_weather": True, "temp": 22, "units": {"temp": "kelvin-ish"}}
    )
    assert data["temp"] is None


def test_out_of_range_observations_are_unavailable() -> None:
    """Reject impossible humidity and bearing values."""
    data = normalize_observations(
        {
            "has_weather": True,
            "humidity": 101,
            "wind_dir_deg": 361,
            "units": {"temp": "°C", "wind": "m/s", "precip": "mm", "press": "hPa"},
        }
    )
    assert data["humidity"] is None
    assert data["wind_dir_deg"] is None


def test_observation_quality_and_timestamp() -> None:
    """Missing weather and invalid timestamps are not fabricated."""
    data = normalize_observations({"has_weather": False, "temp": 4, "timestamp": "bad"})
    assert data["has_weather"] is False
    assert data["temp"] is None
    assert data["timestamp"] is None


def test_observation_staleness_matches_coordinator_policy() -> None:
    """Absent, stale, and implausibly future data are not current."""
    now = 1_000_000
    assert observation_is_current(
        {"has_weather": True, "timestamp": now - 180}, now=now, max_age=180
    )
    assert not observation_is_current(
        {"has_weather": True, "timestamp": now - 181}, now=now, max_age=180
    )
    assert not observation_is_current(
        {"has_weather": True, "timestamp": now + 301}, now=now, max_age=180
    )
    assert not observation_is_current(
        {"has_weather": False, "timestamp": now}, now=now, max_age=180
    )


def test_stable_id_never_uses_station_identity() -> None:
    """Only gateway-level stable IDs can identify the config entry."""
    assert (
        gateway_id({"gateway_id": "GW-1", "id": "GW-2", "station": {"paired_id": 7}})
        == "GW-1"
    )
    assert gateway_id({"station": {"paired_id": 7}}) is None


@pytest.mark.parametrize("host", ["192.168.1.10", "gateway.local", "2001:db8::1"])
def test_valid_hosts(host: str) -> None:
    """Accept valid IPs and DNS names."""
    assert validate_host(host)


@pytest.mark.parametrize(
    "host", ["", "http://gateway", "gateway:80", "bad host", "a..b"]
)
def test_invalid_hosts(host: str) -> None:
    """Reject URLs, ports and malformed hostnames."""
    with pytest.raises(ValueError):
        validate_host(host)


class _Content:
    def __init__(self, body: bytes) -> None:
        self.body = body

    async def iter_chunked(self, size: int):
        for offset in range(0, len(self.body), size):
            yield self.body[offset : offset + size]


class _Response:
    status = 200
    content_length = None

    def __init__(self, body: bytes) -> None:
        self.content = _Content(body)

    async def __aenter__(self) -> _Response:
        return self

    async def __aexit__(self, *args: Any) -> None:
        return None


class _Session:
    def __init__(self, response: _Response) -> None:
        self.response = response
        self.url: str | None = None
        self.options: dict[str, Any] = {}

    def get(self, url: str, **kwargs: Any) -> _Response:
        self.url = url
        self.options = kwargs
        return self.response


@pytest.mark.asyncio
async def test_api_uses_read_only_url_and_blocks_redirects() -> None:
    """Use the requested local path and never follow redirects."""
    session = _Session(_Response(json.dumps({"id": "GW"}).encode()))
    api = GatewayApi("2001:db8::1", 8080, session)  # type: ignore[arg-type]
    assert await api.async_get_info() == {
        "id": "GW",
        "wifi": {},
        "station": {},
        "units": {},
    }
    assert session.url == "http://[2001:db8::1]:8080/api/v1/info"
    assert session.options["allow_redirects"] is False


@pytest.mark.asyncio
async def test_invalid_json_rejected() -> None:
    """Malformed API output raises a typed response error."""
    api = GatewayApi("gateway.local", 80, _Session(_Response(b"<html>")))  # type: ignore[arg-type]
    with pytest.raises(GatewayInvalidResponse):
        await api.async_get_info()


@pytest.mark.asyncio
async def test_timeout_then_recovery() -> None:
    """A timed out poll is reported and a later request can recover."""

    class RecoveringSession(_Session):
        attempts = 0

        def get(self, url: str, **kwargs: Any) -> _Response:
            self.attempts += 1
            if self.attempts == 1:
                raise TimeoutError
            return super().get(url, **kwargs)

    session = RecoveringSession(_Response(b'{"gateway_id":"GW"}'))
    api = GatewayApi("gateway.local", 80, session)  # type: ignore[arg-type]
    with pytest.raises(GatewayConnectionError):
        await api.async_get_info()
    assert await api.async_get_info() == {
        "gateway_id": "GW",
        "wifi": {},
        "station": {},
        "units": {},
    }
