"""Offline validator tests use firmware-shaped local captures."""

from __future__ import annotations

import sys
from pathlib import Path

from custom_components.weatherxm_gateway.api import observation_value
from custom_components.weatherxm_gateway.binary_sensor import binary_sensor_value
from scripts import validate_captures

FIXTURES = Path(__file__).parent / "fixtures"


def test_capture_validator_reuses_parser_and_reports_sensor_values(
    monkeypatch, capsys
) -> None:
    """All three captured endpoints validate and print normalized values."""
    monkeypatch.setattr(validate_captures.time, "time", lambda: 1793577600)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "validate_captures.py",
            "--info",
            str(FIXTURES / "wg1200_info.json"),
            "--observations",
            str(FIXTURES / "wg1200_observations.json"),
            "--status",
            str(FIXTURES / "wg1200_status.json"),
        ],
    )
    assert validate_captures.main() == 0
    output = capsys.readouterr().out
    assert "Gateway model: WXM-WG1200 (stable ID present)" in output
    assert (
        "API units used: {'temp': 'C', 'wind': 'm/s', 'precip': 'mm', 'press': 'hPa'}"
        in output
    )
    assert "temperature: 16.28 °C" in output
    assert "wind_direction: 0.0 °" in output
    assert "packet_reception: 100" in output
    assert "station_type: 1001" in output
    assert "station_firmware: 0" in output
    assert "station_rssi: -74" in output
    assert "wifi_connected: on" in output
    assert "station_communicating: on" in output
    assert "/status weather payload parsed" in output


def test_capture_validator_reports_missing_values_and_sensor_availability(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    """Missing API fields become unavailable and are clearly reported."""
    import json

    monkeypatch.setattr(validate_captures.time, "time", lambda: 1793577600)
    info = json.loads((FIXTURES / "wg1200_info.json").read_text(encoding="utf-8"))
    observations = json.loads(
        (FIXTURES / "wg1200_observations.json").read_text(encoding="utf-8")
    )
    status = json.loads((FIXTURES / "wg1200_status.json").read_text(encoding="utf-8"))
    observations.pop("humidity")
    info["station"].pop("packet_reception")
    status.pop("packet_reception")
    info["wifi"].pop("rssi")
    status.pop("wifi_rssi")
    status.pop("wifi_status")
    info["wifi"].pop("status")
    status.pop("lora_link_ok")
    status.pop("activity_status")

    paths = [
        tmp_path / name for name in ("info.json", "observations.json", "status.json")
    ]
    for path, payload in zip(paths, (info, observations, status), strict=True):
        path.write_text(json.dumps(payload), encoding="utf-8")

    assert validate_captures.validate(*paths) == 0
    output = capsys.readouterr().out
    assert "humidity: unavailable (null or invalid value) %" in output
    assert "wifi_rssi: unavailable (source field absent)" in output
    assert "packet_reception: unavailable (source field absent)" in output
    assert "wifi_connected: not created (source field absent)" in output
    assert "station_communicating: not created (source field absent)" in output
    assert observation_value({"has_weather": True}, "humidity") is None
    assert binary_sensor_value("wifi_connected", {}, {}) is None


def test_capture_validator_separates_parsed_values_from_stale_entity_states(
    monkeypatch, capsys
) -> None:
    """A stale capture remains inspectable while HA sensor state is unavailable."""
    monkeypatch.setattr(validate_captures.time, "time", lambda: 1793578600)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "validate_captures.py",
            "--info",
            str(FIXTURES / "wg1200_info.json"),
            "--observations",
            str(FIXTURES / "wg1200_observations.json"),
            "--status",
            str(FIXTURES / "wg1200_status.json"),
        ],
    )
    assert validate_captures.main() == 0
    output = capsys.readouterr().out
    assert "temperature: 16.28 °C" in output
    assert "Weather sensor availability: observation is stale" in output
    assert "temperature: unavailable (observation is stale)" in output


def test_capture_validator_rejects_non_gateway_info(tmp_path: Path) -> None:
    """An arbitrary JSON document cannot be accepted as a gateway capture."""
    info = tmp_path / "info.json"
    observations = tmp_path / "observations.json"
    status = tmp_path / "status.json"
    info.write_text('{"model":"other","id":"device"}', encoding="utf-8")
    observations.write_text("{}", encoding="utf-8")
    status.write_text("{}", encoding="utf-8")
    try:
        validate_captures.validate(info, observations, status)
    except ValueError as err:
        assert "unsupported WG1200 model" in str(err)
    else:
        raise AssertionError("unsupported device was accepted")
