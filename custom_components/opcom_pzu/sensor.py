"""Senzori OPCOM PZU. Numele sunt în română în `name`; entity_id-urile sunt explicite."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from . import OpcomConfigEntry
from .const import DOMAIN, NAME
from .coordinator import OpcomCoordinator
from .parser import next_cheap_hour

UNIT_MWH = "lei/MWh"
UNIT_KWH = "RON/kWh"

BIG_LISTS = frozenset(
    {
        "azi_15", "azi_30", "azi_60", "maine_15", "maine_30", "maine_60",
        "azi_start_utc", "maine_start_utc",
    }
)


async def async_setup_entry(
    hass: HomeAssistant, entry: OpcomConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    c = entry.runtime_data
    async_add_entities(
        [
            PriceNow(c),
            PriceNowKwh(c),
            DayStat(c, "minim_azi", "Minim azi", "min", "mdi:arrow-down-bold"),
            DayStat(c, "maxim_azi", "Maxim azi", "max", "mdi:arrow-up-bold"),
            DayStat(c, "medie_azi", "Medie azi", "medie", "mdi:approximately-equal"),
            NextCheapHour(c),
        ]
    )


class OpcomEntity(CoordinatorEntity[OpcomCoordinator], SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, c: OpcomCoordinator, key: str, name: str) -> None:
        super().__init__(c)
        self._attr_unique_id = f"{c.config_entry.entry_id}_{key}"
        self._attr_name = name
        self.entity_id = f"sensor.opcom_pzu_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, c.config_entry.entry_id)},
            name=NAME,
            manufacturer="OPCOM",
            model="Piața pentru Ziua Următoare (PZU)",
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def _snap(self):
        return self.coordinator.data.snapshot if self.coordinator.data else None


class PriceNow(OpcomEntity):
    _attr_icon = "mdi:flash"
    _attr_native_unit_of_measurement = UNIT_MWH
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 2
    _unrecorded_attributes = BIG_LISTS

    def __init__(self, c: OpcomCoordinator) -> None:
        super().__init__(c, "pret_acum", "Preț acum")

    @property
    def native_value(self) -> float | None:
        return self._snap.price_now if self._snap else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        d = self.coordinator.data
        if not d:
            return {}
        return {
            **d.snapshot.attributes,
            "ultima_descarcare": d.fetched_at.isoformat() if d.fetched_at else None,
            "eroare": d.last_error,
        }


class PriceNowKwh(OpcomEntity):
    _attr_icon = "mdi:flash-outline"
    _attr_native_unit_of_measurement = UNIT_KWH
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 4

    def __init__(self, c: OpcomCoordinator) -> None:
        super().__init__(c, "pret_acum_kwh", "Preț acum (kWh)")

    @property
    def native_value(self) -> float | None:
        p = self._snap.price_now if self._snap else None
        return None if p is None else round(p / 1000, 5)


class DayStat(OpcomEntity):
    _attr_native_unit_of_measurement = UNIT_MWH
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 2

    def __init__(self, c: OpcomCoordinator, key: str, name: str, field: str, icon: str) -> None:
        super().__init__(c, key, name)
        self._field = field
        self._attr_icon = icon

    @property
    def native_value(self) -> float | None:
        s = self._snap
        mm = s.attributes.get("azi") if s else None
        return mm[self._field] if mm else None


class NextCheapHour(OpcomEntity):
    _attr_icon = "mdi:clock-star-four-points-outline"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, c: OpcomCoordinator) -> None:
        super().__init__(c, "ora_ieftina_urmatoare", "Ora ieftină următoare")

    def _found(self):
        s = self._snap
        return next_cheap_hour(s, dt_util.utcnow()) if s else None

    @property
    def native_value(self):
        f = self._found()
        return f[0] if f else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        f = self._found()
        if not f:
            return {}
        return {"sfarsit": f[1].isoformat(), "pret_mediu_ora_lei_mwh": f[2], "media_zilei_lei_mwh": f[3]}
