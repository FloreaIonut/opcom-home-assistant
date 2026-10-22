"""Integrarea „OPCOM PZU": prețurile pieței pentru ziua următoare, direct în Home Assistant."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import OpcomCoordinator

PLATFORMS = [Platform.SENSOR]

type OpcomConfigEntry = ConfigEntry[OpcomCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: OpcomConfigEntry) -> bool:
    coordinator = OpcomCoordinator(hass, entry)
    # Cache din Store: după repornire senzorii au valori chiar dacă OPCOM nu răspunde.
    await coordinator.async_load_cache()
    # Fără ConfigEntryNotReady: la eroare e „unavailable" + mesaj în log, reîncercare la 10 min.
    await coordinator.async_refresh()
    entry.runtime_data = coordinator
    coordinator.start_ticker()
    entry.async_on_unload(coordinator.stop_ticker)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: OpcomConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_reload(hass: HomeAssistant, entry: OpcomConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
