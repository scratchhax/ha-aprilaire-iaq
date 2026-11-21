"""Base entity for AprilAire Healthy Air devices."""
from __future__ import annotations

from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo, format_mac
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import BRAND, DOMAIN
from .coordinator import AprilAireCoordinator


class AprilAireEntity(CoordinatorEntity[AprilAireCoordinator]):
    """One entity belonging to one cloud device."""

    _attr_has_entity_name = True
    _attr_attribution = "Data from the AprilAire Healthy Air cloud"

    def __init__(self, coordinator: AprilAireCoordinator, device_id: str, key: str | None = None) -> None:
        super().__init__(coordinator)
        self._device_id = device_id
        self._key = key
        self._attr_unique_id = f"{device_id}_{key}" if key else device_id

    @property
    def _device(self) -> dict:
        return (self.coordinator.data or {}).get(self._device_id, {})

    @property
    def available(self) -> bool:
        return super().available and bool(self._device)

    @property
    def device_info(self) -> DeviceInfo:
        dev = self._device
        did = self._device_id
        connections = set()
        if len(did) == 12 and all(c in "0123456789abcdefABCDEF" for c in did):
            connections = {(CONNECTION_NETWORK_MAC, format_mac(did))}
        return DeviceInfo(
            identifiers={(DOMAIN, did)},
            name=dev.get("name") or f"Healthy Air Monitor {did[-4:]}",
            manufacturer=BRAND,
            model=dev.get("model") or "Healthy Air Monitor",
            sw_version=dev.get("firmware"),
            hw_version=dev.get("hardware"),
            connections=connections,
            configuration_url="https://aprilaire.io",
        )
