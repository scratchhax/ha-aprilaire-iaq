"""Sensors for the AprilAire Healthy Air Monitor."""
from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONCENTRATION_PARTS_PER_MILLION,
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import AprilAireCoordinator
from .entity import AprilAireEntity

_DC = SensorDeviceClass
# key -> (name, device class, state class, precision, icon)
MEASUREMENT_META: dict[str, tuple[str, Any, Any, int | None, str]] = {
    "temperature": ("Temperature", getattr(_DC, "TEMPERATURE", None), SensorStateClass.MEASUREMENT, 1, "mdi:thermometer"),
    "humidity": ("Humidity", getattr(_DC, "HUMIDITY", None), SensorStateClass.MEASUREMENT, 1, "mdi:water-percent"),
    "pm25": ("PM2.5", getattr(_DC, "PM25", None), SensorStateClass.MEASUREMENT, 1, "mdi:air-filter"),
    "pm10": ("PM10", getattr(_DC, "PM10", None), SensorStateClass.MEASUREMENT, 1, "mdi:air-filter"),
    "tvoc": ("TVOC", getattr(_DC, "TVOC", None), SensorStateClass.MEASUREMENT, 0, "mdi:molecule"),
    "co2": ("Carbon dioxide", getattr(_DC, "CO2", None), SensorStateClass.MEASUREMENT, 0, "mdi:molecule-co2"),
    "nox": ("Nitrogen oxides", getattr(_DC, "NOX", None), SensorStateClass.MEASUREMENT, 0, "mdi:molecule"),
    "proximity": ("Proximity", None, None, 0, "mdi:motion-sensor"),
}

UNIT_MAP = {
    "C": UnitOfTemperature.CELSIUS,
    "F": UnitOfTemperature.FAHRENHEIT,
    "K": UnitOfTemperature.KELVIN,
    "%": PERCENTAGE,
    "ug/m3": CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    "ppm": CONCENTRATION_PARTS_PER_MILLION,
}

IAQ_ICONS = {
    "Good": "mdi:air-fresh",
    "Fair": "mdi:blur",
    "Concerning": "mdi:weather-hazy",
    "Unhealthy": "mdi:skull-crosswise",
    "Unknown": "mdi:help-circle",
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: AprilAireCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[SensorEntity] = []
    for device_id in coordinator.data or {}:
        entities.extend(AprilAireMeasurementSensor(coordinator, device_id, key) for key in MEASUREMENT_META)
        entities.append(AprilAireAirQualitySensor(coordinator, device_id))
        entities.append(AprilAireWifiSensor(coordinator, device_id))
    async_add_entities(entities)


class AprilAireMeasurementSensor(AprilAireEntity, SensorEntity):
    """One measurement channel reported by the monitor."""

    def __init__(self, coordinator: AprilAireCoordinator, device_id: str, key: str) -> None:
        super().__init__(coordinator, device_id, key)
        name, device_class, state_class, precision, icon = MEASUREMENT_META[key]
        self._attr_name = name
        self._attr_device_class = device_class
        self._attr_state_class = state_class
        self._attr_suggested_display_precision = precision
        self._attr_icon = icon

    @property
    def _measurement(self) -> dict:
        return self._device.get("measurements", {}).get(self._key, {})

    @property
    def native_value(self) -> float | None:
        value = self._measurement.get("value")
        return None if value is None else float(value)

    @property
    def native_unit_of_measurement(self) -> str | None:
        unit = self._measurement.get("unit")
        return UNIT_MAP.get(unit, unit)

    @property
    def available(self) -> bool:
        status = self._measurement.get("status", "reporting")
        return super().available and status in (None, "reporting")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self._measurement
        return {
            "air_quality": data.get("state"),
            "air_quality_code": data.get("state_code"),
            "sensor_status": data.get("status"),
        }


class AprilAireAirQualitySensor(AprilAireEntity, SensorEntity):
    """Overall rating the ring light is showing."""

    def __init__(self, coordinator: AprilAireCoordinator, device_id: str) -> None:
        super().__init__(coordinator, device_id, "air_quality")
        self._attr_name = "Air quality"
        self._attr_icon = IAQ_ICONS["Unknown"]

    @property
    def native_value(self) -> str | None:
        return self._device.get("iaq_state")

    @property
    def icon(self) -> str:
        return IAQ_ICONS.get(self._device.get("iaq_state") or "Unknown", "mdi:air-fresh")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "state_code": self._device.get("iaq_state_code"),
            "reported_at": self._device.get("as_of"),
            "diagnostic_codes": self._device.get("diag") or [],
        }


class AprilAireWifiSensor(AprilAireEntity, SensorEntity):
    """Wi-Fi signal, useful for debugging a marginal install."""

    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: AprilAireCoordinator, device_id: str) -> None:
        super().__init__(coordinator, device_id, "wifi_signal")
        self._attr_name = "Wi-Fi signal"
        self._attr_device_class = getattr(_DC, "SIGNAL_STRENGTH", None)
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = SIGNAL_STRENGTH_DECIBELS_MILLIWATT
        self._attr_icon = "mdi:wifi"

    @property
    def native_value(self) -> float | None:
        rssi = self._device.get("rssi")
        return None if rssi is None else float(rssi)
