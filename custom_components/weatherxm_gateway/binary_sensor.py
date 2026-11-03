"""Connectivity and operational binary sensors."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import GatewayConfigEntry
from .entity import DiagnosticCoordinatorEntity

DESCRIPTIONS = (
    BinarySensorEntityDescription(
        key="wifi_connected",
        translation_key="wifi_connected",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
    ),
    BinarySensorEntityDescription(
        key="mqtt_connected",
        translation_key="mqtt_connected",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
    ),
    BinarySensorEntityDescription(
        key="station_communicating",
        translation_key="station_communicating",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
    ),
    BinarySensorEntityDescription(
        key="station_paired",
        translation_key="station_paired",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
    ),
    BinarySensorEntityDescription(
        key="uplink_active",
        translation_key="uplink_active",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
    ),
    BinarySensorEntityDescription(key="sd_present", translation_key="sd_present"),
    BinarySensorEntityDescription(key="sd_mounted", translation_key="sd_mounted"),
    BinarySensorEntityDescription(
        key="sd_unusable",
        translation_key="sd_unusable",
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GatewayConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up connectivity and operational entities with available fields."""
    data = entry.runtime_data.diagnostics.data
    info = data.get("info", {}) if data else {}
    status = data.get("status", {}) if data else {}
    entities = [
        GatewayBinarySensor(entry, entry.runtime_data.diagnostics, description)
        for description in DESCRIPTIONS
        if binary_sensor_available(description.key, info, status)
    ]
    async_add_entities(entities)


class GatewayBinarySensor(DiagnosticCoordinatorEntity, BinarySensorEntity):
    """Connectivity or device-health state from gateway diagnostics."""

    entity_description: BinarySensorEntityDescription

    def __init__(self, entry, coordinator, description) -> None:
        super().__init__(coordinator, entry)
        self.entity_description = description
        self._attr_unique_id = f"{entry.unique_id}_{description.key}"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def is_on(self) -> bool | None:
        """Return the state only when the source provides a boolean or known enum."""
        return binary_sensor_value(self.entity_description.key, self.info, self.status)


def binary_sensor_available(key: str, info: dict, status: dict) -> bool:
    """Whether the entity has an authoritative source field."""
    wifi = info.get("wifi") if isinstance(info.get("wifi"), dict) else {}
    station = info.get("station") if isinstance(info.get("station"), dict) else {}
    if key == "wifi_connected":
        return "status" in wifi or "wifi_status" in status
    if key == "mqtt_connected":
        return "mqtt_status" in status
    if key == "station_communicating":
        return any(field in status for field in ("lora_link_ok", "activity_status"))
    if key == "station_paired":
        return "is_paired" in station or "is_paired" in status
    if key == "uplink_active":
        return "uplink_active" in status
    if key in {"sd_present", "sd_mounted", "sd_unusable"}:
        return key in status
    return False


def binary_sensor_value(key: str, info: dict, status: dict) -> bool | None:
    """Pure extraction shared with offline capture validation."""
    wifi = info.get("wifi") if isinstance(info.get("wifi"), dict) else {}
    station = info.get("station") if isinstance(info.get("station"), dict) else {}
    if key == "wifi_connected":
        state = wifi.get("status", status.get("wifi_status"))
        if state == "CONNECTED" or (
            isinstance(state, str) and state.startswith("CONNECTED_")
        ):
            return True
        if state in {
            "DISCONNECTED",
            "CONNECTING",
            "CONNECTION_FAILED",
            "DISCONNECTING",
        }:
            return False
        return None
    if key == "mqtt_connected":
        state = status.get("mqtt_status")
        if state == "CONNECTED":
            return True
        if state in {
            "DISCONNECTED",
            "CONNECTING",
            "CONNECTION_FAILED",
            "DISCONNECTING",
            "NONE",
        }:
            return False
        return None
    if key == "station_communicating":
        if "lora_link_ok" in status:
            value = status["lora_link_ok"]
            return value if isinstance(value, bool) else None
        state = status.get("activity_status")
        if isinstance(state, str):
            state = state.lower()
            if state in ("active", "online", "connected", "receiving"):
                return True
            if state in (
                "offline",
                "inactive",
                "idle",
                "disconnected",
                "timeout",
                "no signal",
            ):
                return False
        return None
    if key == "station_paired":
        value = station.get("is_paired", status.get("is_paired"))
        return value if isinstance(value, bool) else None
    if key in {"uplink_active", "sd_present", "sd_mounted", "sd_unusable"}:
        value = status.get(key)
        return value if isinstance(value, bool) else None
    return None
