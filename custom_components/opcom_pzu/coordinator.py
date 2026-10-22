"""Coordinator: descarcă ieri/azi/mâine după nevoie, cache în Store, „acum" la fiecare 15 min."""

from __future__ import annotations

import asyncio
import logging
import random
from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_utc_time_change
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import OpcomClient, OpcomError
from .const import (
    CONF_TIMEZONE,
    CONF_ZONE,
    DEFAULT_TIMEZONE,
    DEFAULT_ZONE,
    DOMAIN,
    FETCH_ATTEMPTS,
    KEEP_DAYS,
    RETRY_PAUSE,
    STORAGE_KEY_PREFIX,
    STORAGE_VERSION,
    TOMORROW_HOUR,
    TOMORROW_RETRY,
    UPDATE_INTERVAL,
)
from .parser import (
    Prices,
    Snapshot,
    build_snapshot,
    days_to_fetch,
    key_plus,
    local_key,
    prices_from_json,
    prices_to_json,
    slots_in_opcom_day,
)

_LOGGER = logging.getLogger(__name__)

# Toleranță: o actualizare programată cu câteva secunde mai devreme nu sare peste reîncercare.
_SLACK = timedelta(seconds=30)


async def _pause(bounds: tuple[float, float]) -> None:
    """Pauză aleatoare (secunde); separată ca testele s-o poată înlocui."""
    await asyncio.sleep(random.uniform(*bounds))


@dataclass
class OpcomData:
    prices: Prices
    snapshot: Snapshot
    fetched_at: datetime | None
    last_error: str | None


class OpcomCoordinator(DataUpdateCoordinator[OpcomData]):
    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(hass, _LOGGER, name=DOMAIN, config_entry=entry, update_interval=UPDATE_INTERVAL)
        conf = {**entry.data, **entry.options}
        self.zone = conf.get(CONF_ZONE, DEFAULT_ZONE)
        try:
            self.tz = ZoneInfo(conf.get(CONF_TIMEZONE, DEFAULT_TIMEZONE))
        except (ZoneInfoNotFoundError, ValueError):
            _LOGGER.error("Fus orar necunoscut, folosesc %s", DEFAULT_TIMEZONE)
            self.tz = ZoneInfo(DEFAULT_TIMEZONE)
        self._client = OpcomClient(async_get_clientsession(hass), self.zone)
        self._store: Store = Store(hass, STORAGE_VERSION, f"{STORAGE_KEY_PREFIX}{entry.entry_id}")
        self.prices: Prices = {}
        self.fetched_at: datetime | None = None
        self.last_error: str | None = None
        self._last_logged: str | None = None
        self._next_try: dict[str, datetime] = {}
        self._unsub_tick: CALLBACK_TYPE | None = None

    # ------------------------------------------------------------------ pornire / oprire

    async def async_load_cache(self) -> None:
        raw = await self._store.async_load()
        if isinstance(raw, dict):
            self.prices = prices_from_json(raw.get("prices"))
            ts = raw.get("fetched_at")
            self.fetched_at = dt_util.parse_datetime(ts) if ts else None
        self.data = self._make_data()

    @callback
    def start_ticker(self) -> None:
        """Valoarea „acum" se recalculează la :00/:15/:30/:45, fără descărcare."""
        self._unsub_tick = async_track_utc_time_change(
            self.hass, self._tick, minute=(0, 15, 30, 45), second=0
        )

    @callback
    def stop_ticker(self) -> None:
        if self._unsub_tick:
            self._unsub_tick()
            self._unsub_tick = None

    @callback
    def _tick(self, _now: datetime) -> None:
        # nu folosim async_set_updated_data: ar marca reușită o actualizare eșuată
        self.data = self._make_data()
        self.async_update_listeners()

    def _make_data(self) -> OpcomData:
        snap = build_snapshot(self.prices, dt_util.utcnow(), self.tz)
        return OpcomData(self.prices, snap, self.fetched_at, self.last_error)

    # ------------------------------------------------------------------ descărcare

    def _needs(self, key: str, now: datetime, azi_key: str) -> bool:
        have = self.prices.get(key)
        complete = bool(have) and len(have) >= slots_in_opcom_day(key)
        if complete:
            return False
        nt = self._next_try.get(key)
        return not (nt and now + _SLACK < nt)

    async def _fetch_with_retry(self, key: str) -> dict[int, float] | None:
        last: OpcomError | None = None
        for attempt in range(FETCH_ATTEMPTS):
            try:
                return await self._client.fetch_day(key)
            except OpcomError as err:
                last = err
                if err.code != "blocked" or attempt == FETCH_ATTEMPTS - 1:
                    break
                await _pause(RETRY_PAUSE)
        assert last is not None
        raise last

    async def _async_update_data(self) -> OpcomData:
        now = dt_util.utcnow()
        azi = local_key(now, self.tz)
        want = days_to_fetch(now, self.tz, TOMORROW_HOUR)
        changed = False
        error: OpcomError | None = None
        for key in want:
            if not self._needs(key, now, azi):
                continue
            tomorrow = key == key_plus(azi, 1)
            try:
                rows = await self._fetch_with_retry(key)
            except OpcomError as err:
                error = err
                self._next_try[key] = now + (TOMORROW_RETRY if tomorrow else UPDATE_INTERVAL)
                self._log_error(err)
                continue
            if not rows:
                _LOGGER.debug("Ziua %s nu e publicată încă", key)
                self._next_try[key] = now + TOMORROW_RETRY
                continue
            self._next_try.pop(key, None)
            if len(rows) != slots_in_opcom_day(key):
                _LOGGER.warning(
                    "Ziua %s are %d sloturi, așteptate %d; reîncerc mai târziu",
                    key, len(rows), slots_in_opcom_day(key),
                )
                self._next_try[key] = now + TOMORROW_RETRY
            if self.prices.get(key) != rows:      # dedup: nu rescriem cache-ul dacă nu s-a schimbat
                self.prices[key] = rows
                changed = True
        if error is None:
            self.last_error = None
            self._last_logged = None
        else:
            self.last_error = error.code
        if changed:
            self.fetched_at = now
            keep = sorted(self.prices)[-KEEP_DAYS:]
            self.prices = {k: self.prices[k] for k in keep}
            await self._store.async_save({"prices": prices_to_json(self.prices), "fetched_at": now.isoformat()})
        data = self._make_data()
        if not self.prices.get(azi):
            # fără prețuri pentru azi (nici din cache): entitățile devin „unavailable"
            raise UpdateFailed(
                f"Nu am prețurile de azi ({error.code if error else 'în așteptare/nepublicat'})"
            )
        return data

    def _log_error(self, err: OpcomError) -> None:
        msg = f"{err.code}: {err}"
        if msg != self._last_logged:
            self._last_logged = msg
            _LOGGER.error("OPCOM PZU, descărcare eșuată (%s)", msg)
        else:
            _LOGGER.debug("OPCOM PZU, încă eșuat (%s)", msg)
