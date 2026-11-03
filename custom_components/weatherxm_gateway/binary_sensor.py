"""Connectivity binary sensors."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
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
        key="station_communicating",
        translation_key="station_communicating",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GatewayConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up connectivity entities only for available source fields."""
    data = entry.runtime_data.diagnostics.data
    info = data.get("info", {}) if data else {}
    status = data.get("status", {}) if data else {}
    entities: list[BinarySensorEntity] = []
    if binary_sensor_available("wifi_connected", info, status):
        entities.append(
            GatewayBinarySensor(entry, entry.runtime_data.diagnostics, DESCRIPTIONS[0])
        )
    if binary_sensor_available("station_communicating", info, status):
        entities.append(
            GatewayBinarySensor(entry, entry.runtime_data.diagnostics, DESCRIPTIONS[1])
        )
    async_add_entities(entities)


class GatewayBinarySensor(DiagnosticCoordinatorEntity, BinarySensorEntity):
    """Connectivity state of Wi-Fi or paired station link."""

    entity_description: BinarySensorEntityDescription

    def __init__(
        self,
        entry: GatewayConfigEntry,
        coordinator,
        description: BinarySensorEntityDescription,
    ) -> None:
        super().__init__(coordinator, entry)
        self.entity_description = description
        self._attr_unique_id = f"{entry.unique_id}_{description.key}"

    @property
    def is_on(self) -> bool | None:
        """Return connection state when its source is reliable."""
        return binary_sensor_value(self.entity_description.key, self.info, self.status)


def binary_sensor_available(key: str, info: dict, status: dict) -> bool:
    """Whether the binary sensor has an authoritative source field."""
    wifi = info.get("wifi") if isinstance(info.get("wifi"), dict) else {}
    if key == "wifi_connected":
        return "status" in wifi or "wifi_status" in status
    if key == "station_communicating":
        return any(field in status for field in ("lora_link_ok", "activity_status"))
    return False


def binary_sensor_value(key: str, info: dict, status: dict) -> bool | None:
    """Shared binary sensor state extraction used by entities and validator."""
    wifi = info.get("wifi") if isinstance(info.get("wifi"), dict) else {}
    if key == "wifi_connected":
        state = wifi.get("status", status.get("wifi_status"))
        if not isinstance(state, str):
            return None
        return state == "CONNECTED" or state.startswith("CONNECTED_")
    if key == "station_communicating":
        if "lora_link_ok" in status:
            return (
                status["lora_link_ok"]
                if isinstance(status["lora_link_ok"], bool)
                else None
            )
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
