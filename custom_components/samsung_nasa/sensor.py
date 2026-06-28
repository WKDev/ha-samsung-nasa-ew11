# 실외기 센서 엔티티: 실외온도/순시전력/누적에너지/에러코드
"""Sensor platform for Samsung NASA outdoor units."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, SIGNAL_DEVICE_DISCOVERED, SIGNAL_STATE_UPDATED
from .gateway import DeviceState, SamsungNasaGateway


@dataclass(frozen=True, kw_only=True)
class SamsungSensorDescription(SensorEntityDescription):
    value_fn: Callable[[DeviceState], Optional[float | int]] = lambda d: None


OUTDOOR_SENSORS: tuple[SamsungSensorDescription, ...] = (
    SamsungSensorDescription(
        key="outdoor_temp",
        translation_key="outdoor_temp",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.outdoor_temp,
    ),
    SamsungSensorDescription(
        key="instantaneous_power",
        translation_key="instantaneous_power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.instantaneous_power,
    ),
    SamsungSensorDescription(
        key="cumulative_energy",
        translation_key="cumulative_energy",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda d: d.cumulative_energy,
    ),
    SamsungSensorDescription(
        key="error_code",
        translation_key="error_code",
        value_fn=lambda d: d.error_code,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    gateway: SamsungNasaGateway = hass.data[DOMAIN][entry.entry_id]

    @callback
    def _discovered(device: DeviceState) -> None:
        if gateway.is_outdoor(device.klass):
            async_add_entities(
                SamsungSensor(gateway, device, desc) for desc in OUTDOOR_SENSORS
            )

    entry.async_on_unload(async_dispatcher_connect(hass, SIGNAL_DEVICE_DISCOVERED, _discovered))

    for device in list(gateway.devices.values()):
        if gateway.is_outdoor(device.klass):
            async_add_entities(SamsungSensor(gateway, device, desc) for desc in OUTDOOR_SENSORS)


class SamsungSensor(SensorEntity):
    """A single outdoor-unit sensor."""

    _attr_has_entity_name = True
    entity_description: SamsungSensorDescription

    def __init__(
        self, gateway: SamsungNasaGateway, device: DeviceState, description: SamsungSensorDescription
    ) -> None:
        self._device = device
        self.entity_description = description
        self._attr_unique_id = f"{DOMAIN}_{device.address}_{description.key}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, device.address)},
            "name": f"Samsung ODU {device.address}",
            "manufacturer": "Samsung",
            "model": "NASA outdoor unit",
        }

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{SIGNAL_STATE_UPDATED}_{self._device.address}",
                self.async_write_ha_state,
            )
        )

    @property
    def native_value(self):
        return self.entity_description.value_fn(self._device)
