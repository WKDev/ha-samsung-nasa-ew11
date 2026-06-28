# 실내기 climate 엔티티: 전원/모드/설정온도/팬/스윙 읽기 및 제어
"""Climate platform for Samsung NASA indoor units."""

from __future__ import annotations

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import nasa
from .const import DOMAIN, SIGNAL_DEVICE_DISCOVERED, SIGNAL_STATE_UPDATED
from .gateway import DeviceState, SamsungNasaGateway

# Samsung Mode <-> HA HVACMode (when powered on)
_MODE_TO_HVAC = {
    nasa.Mode.Auto: HVACMode.AUTO,
    nasa.Mode.Cool: HVACMode.COOL,
    nasa.Mode.Dry: HVACMode.DRY,
    nasa.Mode.Fan: HVACMode.FAN_ONLY,
    nasa.Mode.Heat: HVACMode.HEAT,
}
_HVAC_TO_MODE = {v: k for k, v in _MODE_TO_HVAC.items()}

_FAN_TO_NASA = {
    "auto": nasa.FanMode.Auto,
    "low": nasa.FanMode.Low,
    "mid": nasa.FanMode.Mid,
    "high": nasa.FanMode.High,
    "turbo": nasa.FanMode.Turbo,
}
_NASA_TO_FAN = {v: k for k, v in _FAN_TO_NASA.items()}

SWING_OFF = "off"
SWING_VERTICAL = "vertical"
SWING_HORIZONTAL = "horizontal"
SWING_BOTH = "both"


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    gateway: SamsungNasaGateway = hass.data[DOMAIN][entry.entry_id]

    @callback
    def _discovered(device: DeviceState) -> None:
        if gateway.is_indoor(device.klass):
            async_add_entities([SamsungClimate(gateway, device)])

    entry.async_on_unload(async_dispatcher_connect(hass, SIGNAL_DEVICE_DISCOVERED, _discovered))

    # devices discovered before this platform attached
    for device in list(gateway.devices.values()):
        if gateway.is_indoor(device.klass):
            async_add_entities([SamsungClimate(gateway, device)])


class SamsungClimate(ClimateEntity):
    """A Samsung NASA indoor unit."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_target_temperature_step = 0.5
    _attr_min_temp = 16
    _attr_max_temp = 30
    _attr_hvac_modes = [HVACMode.OFF, *_MODE_TO_HVAC.values()]
    _attr_fan_modes = list(_FAN_TO_NASA.keys())
    _attr_swing_modes = [SWING_OFF, SWING_VERTICAL, SWING_HORIZONTAL, SWING_BOTH]
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.SWING_MODE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )

    def __init__(self, gateway: SamsungNasaGateway, device: DeviceState) -> None:
        self._gateway = gateway
        self._device = device
        self._attr_unique_id = f"{DOMAIN}_{device.address}_climate"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, device.address)},
            "name": f"Samsung A/C {device.address}",
            "manufacturer": "Samsung",
            "model": "NASA indoor unit",
        }

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{SIGNAL_STATE_UPDATED}_{self._device.address}",
                self.async_write_ha_state,
            )
        )

    # ----- state ----------------------------------------------------------

    @property
    def current_temperature(self):
        return self._device.room_temp

    @property
    def target_temperature(self):
        return self._device.target_temp

    @property
    def hvac_mode(self):
        if self._device.power is False:
            return HVACMode.OFF
        if self._device.mode is None:
            return None
        return _MODE_TO_HVAC.get(self._device.mode)

    @property
    def fan_mode(self):
        return _NASA_TO_FAN.get(self._device.fan_mode)

    @property
    def swing_mode(self):
        v = self._device.swing_vertical
        h = self._device.swing_horizontal
        if v and h:
            return SWING_BOTH
        if v:
            return SWING_VERTICAL
        if h:
            return SWING_HORIZONTAL
        return SWING_OFF

    # ----- commands -------------------------------------------------------

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        if hvac_mode == HVACMode.OFF:
            await self._send([_msg(nasa.MessageNumber.ENUM_in_operation_power, 0)])
            return
        mode = _HVAC_TO_MODE[hvac_mode]
        # match firmware behaviour: setting a mode also powers the unit on
        await self._send(
            [
                _msg(nasa.MessageNumber.ENUM_in_operation_mode, int(mode)),
                _msg(nasa.MessageNumber.ENUM_in_operation_power, 1),
            ]
        )

    async def async_turn_on(self) -> None:
        await self._send([_msg(nasa.MessageNumber.ENUM_in_operation_power, 1)])

    async def async_turn_off(self) -> None:
        await self._send([_msg(nasa.MessageNumber.ENUM_in_operation_power, 0)])

    async def async_set_temperature(self, **kwargs) -> None:
        temp = kwargs.get(ATTR_TEMPERATURE)
        if temp is None:
            return
        await self._send([_msg(nasa.MessageNumber.VAR_in_temp_target_f, int(round(temp * 10)))])

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        value = nasa.fanmode_to_nasa(_FAN_TO_NASA[fan_mode])
        await self._send([_msg(nasa.MessageNumber.ENUM_in_fan_mode, value)])

    async def async_set_swing_mode(self, swing_mode: str) -> None:
        vertical = 1 if swing_mode in (SWING_VERTICAL, SWING_BOTH) else 0
        horizontal = 1 if swing_mode in (SWING_HORIZONTAL, SWING_BOTH) else 0
        await self._send(
            [
                _msg(nasa.MessageNumber.ENUM_in_louver_hl_swing, vertical),
                _msg(nasa.MessageNumber.ENUM_in_louver_lr_swing, horizontal),
            ]
        )

    async def _send(self, messages: list[nasa.MessageSet]) -> None:
        await self._gateway.async_send(self._device.address, messages)


def _msg(number: int, value: int) -> nasa.MessageSet:
    """Build a MessageSet (type is derived automatically from the number)."""
    msg = nasa.MessageSet(number)
    msg.value = value
    return msg
