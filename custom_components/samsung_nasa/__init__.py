# 통합 진입점: config entry 설정/해제 및 게이트웨이 수명주기 관리
"""The Samsung NASA (EW11) integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .gateway import SamsungNasaGateway

PLATFORMS: list[Platform] = [Platform.CLIMATE, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Samsung NASA from a config entry."""
    gateway = SamsungNasaGateway(hass, entry)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = gateway

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await gateway.async_start()
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    gateway: SamsungNasaGateway = hass.data[DOMAIN].pop(entry.entry_id)
    await gateway.async_stop()
    return unload_ok
