"""Tests for the opt-in weather-condition estimator."""

from __future__ import annotations

import pytest

from custom_components.weatherxm_gateway.weather import estimated_condition


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        ({"has_weather": False, "precip_rate": 9}, None),
        ({"has_weather": True, "precip_rate": 0.0}, None),
        ({"has_weather": True, "precip_rate": 0.1}, "rainy"),
        ({"has_weather": True, "precip_rate": 7.5}, "pouring"),
        ({"has_weather": True, "wind_speed": 40 / 3.6}, "windy"),
        ({"has_weather": True, "irradiance": 500}, "sunny"),
        ({"has_weather": True, "irradiance": 300, "uv": 6}, "sunny"),
        # UV alone is not evidence that the sky is sunny.
        ({"has_weather": True, "uv": 10}, None),
        # No cloud-cover API means no invented partly-cloudy/clear-night fallback.
        ({"has_weather": True, "temp": 25, "humidity": 30}, None),
        ({"has_weather": True, "precip_rate": 1, "wind_speed": 20}, "rainy"),
    ],
)
def test_estimated_condition(data: dict, expected: str | None) -> None:
    """Only emit estimates supported by current local weather readings."""
    assert estimated_condition(data) == expected
