"""Logica pură OPCOM PZU (fără Home Assistant): CSV, fus orar, grila zilei locale.

Port fidel al `opcom-core.js` din varianta din nodered/ (corecția de fus orar, 22.10.2026):

* OPCOM publică intervalele în CET/CEST (ora României minus 1 h): intervalul 1 al
  zilei OPCOM Z = 00:00-00:15 CET/CEST al lui Z = 01:00-01:15 ora României.
* Fiecare slot are `ts_utc` = 00:00 CET/CEST a zilei OPCOM + (interval - 1) * 15 min.
* Ziua locală (Europe/Bucharest) = sloturile 93-96 din ziua OPCOM de ieri + restul
  zilei de azi; 92 / 96 / 100 de sloturi (zile de 23 / 24 / 25 de ore).
* „mâine" e gol până sunt publicate prețurile zilei OPCOM de mâine.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

UTC = timezone.utc
SLOT = timedelta(minutes=15)
OPCOM_TZ = "Europe/Berlin"
CSV_URL = "https://www.opcom.ro/rapoarte-pzu-raportPIP-export-csv/{dd}/{mm}/{yyyy}/ro?resolution=15"

# Prețuri: { "AAAA-LL-ZZ" (ziua OPCOM): { interval: preț lei/MWh } }
Prices = dict[str, dict[int, float]]


# --------------------------------------------------------------------------- utilitare


def r2(x: float) -> float:
    """Rotunjire la 2 zecimale ca Math.round(x*100)/100 din JS (jumătățile în sus)."""
    return math.floor(x * 100 + 0.5) / 100


def day_key(d: date) -> str:
    return d.isoformat()


def key_to_date(key: str) -> date:
    return date.fromisoformat(key)


def key_plus(key: str, n: int) -> str:
    return day_key(key_to_date(key) + timedelta(days=n))


def day_url(key: str) -> str:
    d = key_to_date(key)
    return CSV_URL.format(dd=f"{d.day:02d}", mm=f"{d.month:02d}", yyyy=d.year)


def iso(t: datetime) -> str:
    """ISO UTC fără secunde, ca în Node-RED: 2026-10-21T21:00Z."""
    return t.astimezone(UTC).strftime("%Y-%m-%dT%H:%MZ")


def _midnight_utc(d: date, tz: ZoneInfo) -> datetime:
    return datetime(d.year, d.month, d.day, tzinfo=tz).astimezone(UTC)


def opcom_day_start(key: str) -> datetime:
    """00:00 CET/CEST al zilei OPCOM, în UTC."""
    return _midnight_utc(key_to_date(key), ZoneInfo(OPCOM_TZ))


def local_day_start(key: str, tz: ZoneInfo) -> datetime:
    """00:00 ora locală a zilei locale, în UTC."""
    return _midnight_utc(key_to_date(key), tz)


def local_key(t: datetime, tz: ZoneInfo) -> str:
    """Ziua locală (cheie AAAA-LL-ZZ) a unui instant."""
    return day_key(t.astimezone(tz).date())


def slot_start(key: str, interval: int) -> datetime:
    """Începutul slotului `interval` al zilei OPCOM `key` (UTC)."""
    return opcom_day_start(key) + (interval - 1) * SLOT


def slots_in_opcom_day(key: str) -> int:
    return int((opcom_day_start(key_plus(key, 1)) - opcom_day_start(key)) / SLOT)


def slots_in_local_day(key: str, tz: ZoneInfo) -> int:
    return int((local_day_start(key_plus(key, 1), tz) - local_day_start(key, tz)) / SLOT)


# --------------------------------------------------------------------------- CSV


def parse_csv(text: str, zone: str = "Romania") -> dict[int, float]:
    """Rândurile `"Romania","interval","preț",...` -> {interval: preț lei/MWh}.

    Același format ca `salveaza.js`: coloana 1 = interval, coloana 2 = preț.
    """
    out: dict[int, float] = {}
    prefix = f'"{zone}"'
    for line in str(text).replace("\r", "").split("\n"):
        line = line.strip()
        if not line.startswith(prefix):
            continue
        cols = [c.replace('"', "").strip() for c in line.split(",")]
        try:
            interval = int(cols[1])
            price = float(cols[2])
        except (IndexError, ValueError):
            continue
        out[interval] = price
    return out


_BLOCK_RE = re.compile(r"request rejected|access denied|\bblocked\b|captcha|forbidden", re.I)


def classify_response(status: int, text: str, zone: str = "Romania") -> str:
    """Clasifică un răspuns: ok | empty | blocked | not_csv | http_error.

    * ok         - conține rânduri de preț;
    * empty      - 200 fără rânduri (corp gol sau doar antet): ziua nu e publicată încă;
    * blocked    - 401/403/406/429 sau pagină „Blocked" / WAF;
    * not_csv    - 200 cu altceva decât CSV (HTML intermitent);
    * http_error - alt cod HTTP.
    """
    if parse_csv(text, zone):
        return "ok" if status == 200 else "http_error"
    head = text[:4000]
    if status in (401, 403, 406, 429) or _BLOCK_RE.search(head):
        return "blocked"
    if status != 200:
        return "http_error"
    stripped = head.lstrip()
    if not stripped:
        return "empty"
    if stripped.startswith('"') and "PIP" in stripped[:200]:
        return "empty"
    return "not_csv"


# --------------------------------------------------------------------------- grila


@dataclass
class Grid:
    start: datetime
    starts: list[datetime] = field(default_factory=list)
    p15: list[float | None] = field(default_factory=list)
    interval_opcom: list[int | None] = field(default_factory=list)

    @property
    def iso(self) -> list[str]:
        return [iso(t) for t in self.starts]


def build_grid(prices: Prices, local_key_: str, tz: ZoneInfo) -> Grid:
    """Grila zilei locale (92/96/100 sloturi) umplută din ieri + azi OPCOM; lipsă = None."""
    start = local_day_start(local_key_, tz)
    n = slots_in_local_day(local_key_, tz)
    by_ts: dict[datetime, float] = {}
    by_iv: dict[datetime, int] = {}
    for z in (key_plus(local_key_, -1), local_key_):
        for interval, price in (prices.get(z) or {}).items():
            t = slot_start(z, interval)
            by_ts[t] = price
            by_iv[t] = interval
    g = Grid(start=start)
    for i in range(n):
        t = start + i * SLOT
        g.starts.append(t)
        g.p15.append(by_ts.get(t))
        g.interval_opcom.append(by_iv.get(t))
    return g


def averages(values: list[float | None], n: int) -> list[float | None]:
    out: list[float | None] = []
    for i in range(0, len(values), n):
        v = [x for x in values[i : i + n] if x is not None]
        out.append(r2(sum(v) / len(v)) if v else None)
    return out


def min_max(values: list[float | None]) -> dict[str, float] | None:
    v = [x for x in values if x is not None]
    if not v:
        return None
    return {"min": min(v), "max": max(v), "medie": r2(sum(v) / len(v))}


@dataclass
class Snapshot:
    """Tot ce publică senzorul principal la un moment dat."""

    azi_key: str
    maine_key: str
    price_now: float | None
    interval: int
    interval_opcom: int | None
    azi: Grid
    maine: Grid | None
    attributes: dict[str, Any]


def build_snapshot(prices: Prices, now: datetime, tz: ZoneInfo) -> Snapshot:
    """Echivalentul `ocConstruieste`: preț acum + atribute (nume identice cu Node-RED)."""
    now = now.astimezone(UTC)
    azi_key = local_key(now, tz)
    maine_key = key_plus(azi_key, 1)
    azi = build_grid(prices, azi_key, tz)
    maine_ok = len(prices.get(maine_key) or {}) > 0
    maine = build_grid(prices, maine_key, tz) if maine_ok else None
    idx = int((now - azi.start) / SLOT)
    price_now = azi.p15[idx] if 0 <= idx < len(azi.p15) else None
    iv_opcom = azi.interval_opcom[idx] if 0 <= idx < len(azi.p15) else None
    m15 = maine.p15 if maine else []
    attrs: dict[str, Any] = {
        "interval": idx + 1,
        "interval_opcom": iv_opcom,
        "azi": min_max(azi.p15),
        "maine": min_max(m15),
        "maine_disponibil": maine_ok,
        "data_azi": azi_key,
        "data_maine": maine_key,
        "azi_15": azi.p15,
        "azi_30": averages(azi.p15, 2),
        "azi_60": averages(azi.p15, 4),
        "maine_15": m15,
        "maine_30": averages(m15, 2),
        "maine_60": averages(m15, 4),
        "azi_start_utc": azi.iso,
        "maine_start_utc": maine.iso if maine else [],
    }
    return Snapshot(azi_key, maine_key, price_now, idx + 1, iv_opcom, azi, maine, attrs)


def next_cheap_hour(
    snap: Snapshot, now: datetime
) -> tuple[datetime, datetime, float, float] | None:
    """Începutul următoarei ore (de 4 sloturi) cu media sub media zilei ei.

    Întoarce (început, sfârșit, preț mediu oră, media zilei) sau None.
    """
    now = now.astimezone(UTC)
    for grid in (snap.azi, snap.maine):
        if grid is None:
            continue
        mm = min_max(grid.p15)
        if not mm:
            continue
        hours = averages(grid.p15, 4)
        for h, avg in enumerate(hours):
            start = grid.starts[h * 4]
            end = start + 4 * SLOT
            if avg is not None and start > now and avg < mm["medie"]:
                return start, end, avg, mm["medie"]
    return None


def days_to_fetch(now: datetime, tz: ZoneInfo, tomorrow_hour: int = 14) -> list[str]:
    """Zilele OPCOM de cerut: ieri (sloturile 93-96 = 00:00-01:00 locală), azi, iar mâine
    după `tomorrow_hour` ora locală."""
    now = now.astimezone(UTC)
    azi = local_key(now, tz)
    days = [key_plus(azi, -1), azi]
    if now.astimezone(tz).hour >= tomorrow_hour:
        days.append(key_plus(azi, 1))
    return days


def prices_to_json(prices: Prices) -> dict[str, list[list[float]]]:
    return {k: [[i, p] for i, p in sorted(v.items())] for k, v in prices.items()}


def prices_from_json(raw: Any) -> Prices:
    out: Prices = {}
    if not isinstance(raw, dict):
        return out
    for k, rows in raw.items():
        try:
            key_to_date(k)
            out[k] = {int(i): float(p) for i, p in rows}
        except (ValueError, TypeError):
            continue
    return out
