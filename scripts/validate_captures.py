#!/usr/bin/env python3
"""Validate locally captured WG1200 endpoint JSON with integration code."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

# Running this file directly puts `scripts/`, rather than the checkout root, on
# sys.path. Import the integration package from this checkout without installing it.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from custom_components.weatherxm_gateway.api import (
    gateway_id,
    info_model,
    normalize_info,
    normalize_observations,
    normalize_status,
    observation_freshness,
    observation_is_current,
    observation_units,
    observation_value,
    supported_model,
)
from custom_components.weatherxm_gateway.binary_sensor import (
    binary_sensor_available,
    binary_sensor_value,
)
from custom_components.weatherxm_gateway.sensor import (
    DIAGNOSTIC_SENSORS,
    WEATHER_SENSORS,
    diagnostic_available,
    diagnostic_native_value,
)


def _load(path: Path) -> dict[str, Any]:
    """Read one captured JSON object."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as err:
        raise ValueError(f"{path}: cannot read JSON ({err})") from err
    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected a JSON object")
    return data


def validate(info_path: Path, observations_path: Path, status_path: Path) -> int:
    """Print parsed sensor values; return nonzero for unusable captures."""
    raw_info = _load(info_path)
    raw_observations = _load(observations_path)
    raw_status = _load(status_path)
    info = normalize_info(raw_info)
    observations = normalize_observations(raw_observations, info)
    status = normalize_status(raw_status)

    identity = gateway_id(info)
    model = info_model(info)
    if identity is None:
        raise ValueError(f"{info_path}: no stable gateway id (id/gateway_id)")
    if not supported_model(model):
        raise ValueError(f"{info_path}: unsupported WG1200 model {model!r}")

    current = observation_is_current(
        observations, now=time.time(), max_age=max(180, 3 * 20)
    )
    print(f"Gateway model: {model} (stable ID present)")
    print(f"API units used: {observation_units(raw_observations, info)}")
    print("Normalized observations (canonical native units):")
    parsed_observations = dict(observations)
    parsed_observations["has_weather"] = True
    for description in WEATHER_SENSORS:
        value = observation_value(parsed_observations, description.field)
        unit = description.native_unit_of_measurement or ""
        state = (
            str(value) if value is not None else "unavailable (null or invalid value)"
        )
        print(f"  {description.key}: {state}{f' {unit}' if unit else ''}")

    freshness = observation_freshness(
        observations, now=time.time(), max_age=max(180, 3 * 20)
    )
    print(f"Weather sensor availability: {freshness}")
    entity_observations = dict(observations)
    entity_observations["has_weather"] = current
    for description in WEATHER_SENSORS:
        value = observation_value(entity_observations, description.field)
        if value is not None:
            state = "available"
        elif current:
            state = "unavailable (null or invalid value)"
        else:
            state = f"unavailable ({freshness})"
        print(f"  {description.key}: {state}")

    print("Diagnostic sensors:")
    diagnostic_data = {"info": info, "status": status}
    for description in DIAGNOSTIC_SENSORS:
        value = diagnostic_native_value(description, info, status, observations)
        available = diagnostic_available(diagnostic_data, description)
        state = (
            str(value)
            if available and value is not None
            else "unavailable (source field absent)"
            if not available
            else "unavailable (null or invalid value)"
        )
        print(f"  {description.key}: {state}")

    print("Connectivity binary sensors:")
    for key in ("wifi_connected", "station_communicating"):
        if not binary_sensor_available(key, info, status):
            state = "not created (source field absent)"
        else:
            value = binary_sensor_value(key, info, status)
            state = "unavailable" if value is None else "on" if value else "off"
        print(f"  {key}: {state}")

    # The status endpoint contains the same weather data under `weather`; run it
    # through the exact observation normalizer too, as a firmware schema check.
    status_weather = status.get("weather")
    if isinstance(status_weather, dict):
        normalized_status_weather = normalize_observations(status_weather, info)
        print("/status weather payload parsed:")
        print(f"  API units used: {observation_units(status_weather, info)}")
        print(
            f"  has_weather: {normalized_status_weather['has_weather']}; "
            f"temperature: {normalized_status_weather['temp']}"
        )
    elif "weather" in status:
        raise ValueError(f"{status_path}: weather must be a JSON object")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--info", required=True, type=Path, help="/api/v1/info JSON")
    parser.add_argument(
        "--observations", required=True, type=Path, help="/api/v1/observations JSON"
    )
    parser.add_argument("--status", required=True, type=Path, help="/status JSON")
    args = parser.parse_args()
    try:
        return validate(args.info, args.observations, args.status)
    except ValueError as err:
        print(f"Capture validation failed: {err}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
