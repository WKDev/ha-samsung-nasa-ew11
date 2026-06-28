# 디바이스 상태 보관 + NASA Notification 해석 + HA 플랫폼 디스패치 게이트웨이
"""Holds per-address device state and bridges the NASA client to HA entities."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send

from . import nasa
from .client import SamsungNasaClient
from .const import (
    CONF_HOST,
    CONF_PORT,
    KLASS_INDOOR,
    KLASS_OUTDOOR,
    SIGNAL_DEVICE_DISCOVERED,
    SIGNAL_STATE_UPDATED,
)
from .nasa import MessageNumber

_LOGGER = logging.getLogger(__name__)


@dataclass
class DeviceState:
    """Latest known state for one NASA address."""

    address: str
    klass: int
    # indoor / climate
    power: Optional[bool] = None
    mode: Optional[nasa.Mode] = None
    fan_mode: Optional[nasa.FanMode] = None
    target_temp: Optional[float] = None
    room_temp: Optional[float] = None
    swing_vertical: Optional[bool] = None
    swing_horizontal: Optional[bool] = None
    # outdoor / sensors
    outdoor_temp: Optional[float] = None
    instantaneous_power: Optional[float] = None
    cumulative_energy: Optional[float] = None
    error_code: Optional[int] = None
    # raw message cache (for diagnostics)
    raw: dict = field(default_factory=dict)


class SamsungNasaGateway:
    """Owns the client and the device-state registry."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self._hass = hass
        self._entry = entry
        self.devices: dict[str, DeviceState] = {}
        self._client = SamsungNasaClient(
            entry.data[CONF_HOST], entry.data[CONF_PORT], self._on_packet
        )

    async def async_start(self) -> None:
        await self._client.start()

    async def async_stop(self) -> None:
        await self._client.stop()

    # ----- inbound --------------------------------------------------------

    async def _on_packet(self, packet: nasa.Packet) -> None:
        if packet.command.data_type != nasa.DataType.Notification:
            return
        source = packet.sa.to_string()
        device = self._ensure_device(source, packet.sa.klass)
        for message in packet.messages:
            self._apply_message(device, message)
        async_dispatcher_send(self._hass, f"{SIGNAL_STATE_UPDATED}_{source}")

    def _ensure_device(self, address: str, klass: int) -> DeviceState:
        device = self.devices.get(address)
        if device is None:
            device = DeviceState(address=address, klass=klass)
            self.devices[address] = device
            _LOGGER.info("Discovered NASA device %s (class %#04x)", address, klass)
            async_dispatcher_send(self._hass, SIGNAL_DEVICE_DISCOVERED, device)
        return device

    def _apply_message(self, device: DeviceState, message: nasa.MessageSet) -> None:
        number = message.message_number
        value = message.value
        device.raw[number] = value

        if number == MessageNumber.VAR_in_temp_room_f:
            device.room_temp = value / 10.0
        elif number == MessageNumber.VAR_in_temp_target_f:
            device.target_temp = value / 10.0
        elif number == MessageNumber.ENUM_in_operation_power:
            device.power = value != 0
        elif number == MessageNumber.ENUM_in_operation_mode:
            device.mode = nasa.operation_mode_to_mode(value)
        elif number == MessageNumber.ENUM_in_fan_mode:
            device.fan_mode = nasa.enum_to_fanmode(value)
        elif number == MessageNumber.ENUM_in_louver_hl_swing:
            device.swing_vertical = value == 1
        elif number == MessageNumber.ENUM_in_louver_lr_swing:
            device.swing_horizontal = value == 1
        elif number == MessageNumber.VAR_out_sensor_airout:
            device.outdoor_temp = nasa._s16(value) / 10.0
        elif number == MessageNumber.LVAR_OUT_CONTROL_WATTMETER_1W_1MIN_SUM:
            device.instantaneous_power = float(value)
        elif number == MessageNumber.LVAR_OUT_CONTROL_WATTMETER_ALL_UNIT_ACCUM:
            device.cumulative_energy = float(value)
        elif number == MessageNumber.VAR_out_error_code:
            device.error_code = int(value)

    # ----- outbound (control) --------------------------------------------

    async def async_send(self, address: str, messages: list[nasa.MessageSet]) -> None:
        await self._client.send_request(nasa.Address.parse(address), messages)

    @staticmethod
    def is_indoor(klass: int) -> bool:
        return klass == KLASS_INDOOR

    @staticmethod
    def is_outdoor(klass: int) -> bool:
        return klass == KLASS_OUTDOOR
