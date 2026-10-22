"""Teste pure pe parser.py (fără HA). Aceleași aserțiuni ca testele din varianta din nodered/."""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "custom_components" / "opcom_pzu"))
import parser as p  # noqa: E402

FIX = Path(__file__).resolve().parent / "fixtures"
UTC = timezone.utc
RO = ZoneInfo("Europe/Bucharest")


def utc(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def csv(name: str) -> str:
    return (FIX / name).read_text(encoding="utf-8")


def csv60(name: str) -> dict[int, float]:
    out = {}
    for line in csv(name).splitlines():
        import re
        m = re.match(r'^"(\d+)","([\d.]+)","PT60M"', line)
        if m:
            out[int(m[1])] = float(m[2])
    return out


@pytest.fixture(scope="module")
def prices():
    return {
        "2026-10-21": p.parse_csv(csv("21-10-2026_15.csv")),
        "2026-10-22": p.parse_csv(csv("22-10-2026_15.csv")),
    }


@pytest.fixture(scope="module")
def snap(prices):
    return p.build_snapshot(prices, utc("2026-10-22T18:30:00Z"), RO)   # 21:30 EEST


def test_parse_real_csv(prices):
    assert len(prices["2026-10-22"]) == 96 and len(prices["2026-10-21"]) == 96
    assert prices["2026-10-22"][1] == 1020.97


def test_1930_state(prices, snap):
    assert snap.price_now == prices["2026-10-22"][83] == 1638.94
    assert snap.attributes["interval_opcom"] == 83 and snap.attributes["interval"] == 87


def test_hour_21_and_min_and_midnight(prices, snap):
    a = snap.attributes
    assert a["azi_60"][21] == 1532.03
    i = a["azi_60"].index(min(a["azi_60"]))
    assert i == 5 and a["azi_60"][5] == 968.94
    c60, c60y = csv60("22-10-2026_60.csv"), csv60("21-10-2026_60.csv")
    for h in range(1, 24):
        assert abs(a["azi_60"][h] - c60[h]) <= 0.011, h
    assert abs(a["azi_60"][0] - c60y[24]) <= 0.011
    assert a["azi_15"][0] == prices["2026-10-21"][93]
    assert a["azi_60"][0] == 1295.10


def test_known_hourly_values():
    c60 = csv60("22-10-2026_60.csv")
    for k, v in {1: 1019.27, 5: 968.94, 9: 1718.78, 20: 1550.58, 21: 1532.03, 22: 1527.90, 23: 1482.59}.items():
        assert c60[k] == v


def test_lists_and_attribute_names(snap):
    a = snap.attributes
    assert [len(a[k]) for k in ("azi_15", "azi_30", "azi_60", "azi_start_utc")] == [96, 48, 24, 96]
    assert [len(a[k]) for k in ("maine_15", "maine_60", "maine_start_utc")] == [0, 0, 0]
    assert a["azi_start_utc"][0] == "2026-10-21T21:00Z" and a["azi_start_utc"][95] == "2026-10-22T20:45Z"
    assert a["data_azi"] == "2026-10-22" and a["data_maine"] == "2026-10-23" and a["maine_disponibil"] is False
    for k in ("azi", "maine", "maine_disponibil", "data_azi", "data_maine", "azi_15", "azi_30", "azi_60",
              "maine_15", "maine_30", "maine_60", "interval", "interval_opcom", "azi_start_utc", "maine_start_utc"):
        assert k in a
    assert list(a["azi"]) == ["min", "max", "medie"] and a["maine"] is None


def test_tomorrow_real_csv(prices):
    pr = {**prices, "2026-10-23": p.parse_csv(csv("23-10-2026_15.csv"))}
    s = p.build_snapshot(pr, utc("2026-10-22T19:00:00Z"), RO)
    a = s.attributes
    assert a["maine_disponibil"] and [len(a["maine_15"]), len(a["maine_30"]), len(a["maine_60"])] == [96, 48, 24]
    assert a["maine_15"][0] == prices["2026-10-22"][93] and a["maine_start_utc"][0] == "2026-10-22T21:00Z"


def test_without_yesterday_stays_aligned(prices):
    s = p.build_snapshot({"2026-10-22": prices["2026-10-22"]}, utc("2026-10-22T18:30:00Z"), RO)
    assert s.attributes["azi_15"][0] is None and s.attributes["azi_60"][0] is None
    assert s.attributes["azi_60"][21] == 1532.03 and s.price_now == 1638.94


def synth(key, n):
    st = p.opcom_day_start(key)
    return {i: pret(st + (i - 1) * p.SLOT) for i in range(1, n + 1)}


def pret(t):
    return round(t.timestamp() / 900) % 100000 + 0.5


def contiguous(isos):
    for a, b in zip(isos, isos[1:]):
        assert utc(b) - utc(a) == p.SLOT


def fill(keys):
    return {k: synth(k, p.slots_in_opcom_day(k)) for k in keys}


def test_25h_day():
    pr = fill(["2026-10-23", "2026-10-24", "2026-10-25", "2026-10-26"])
    assert len(pr["2026-10-25"]) == 100
    a = p.build_snapshot(pr, utc("2026-10-25T10:00:00Z"), RO).attributes
    assert [len(a[k]) for k in ("azi_15", "azi_30", "azi_60", "azi_start_utc")] == [100, 50, 25, 100]
    assert a["azi_start_utc"][0] == "2026-10-24T21:00Z" and a["azi_start_utc"][99] == "2026-10-25T21:45Z"
    contiguous(a["azi_start_utc"])
    assert None not in a["azi_15"]
    for s, v in zip(a["azi_start_utc"], a["azi_15"]):
        assert v == pret(utc(s))
    assert a["azi_15"][:4] == [pr["2026-10-24"][i] for i in (93, 94, 95, 96)]
    assert a["azi_15"][96:] == [pr["2026-10-25"][i] for i in (93, 94, 95, 96)]
    b = p.build_snapshot(pr, utc("2026-10-26T10:00:00Z"), RO).attributes
    assert b["azi_15"][:4] == [pr["2026-10-25"][i] for i in (97, 98, 99, 100)] and len(b["azi_15"]) == 96
    assert b["azi_start_utc"][0] == "2026-10-25T22:00Z"


def test_25h_day_intervals():
    pr = fill(["2026-10-23", "2026-10-24", "2026-10-25", "2026-10-26"])
    g = lambda t: p.build_snapshot(pr, utc(t), RO)
    e1, e2 = g("2026-10-25T00:30:00Z"), g("2026-10-25T01:30:00Z")
    assert (e1.interval, e2.interval, e1.interval_opcom, e2.interval_opcom) == (15, 19, 11, 15)
    assert e1.price_now == pret(utc("2026-10-25T00:30:00Z")) and e2.price_now == pret(utc("2026-10-25T01:30:00Z"))
    assert g("2026-10-25T00:59:00Z").interval == 16 and g("2026-10-25T01:00:00Z").interval == 17
    assert g("2026-10-24T23:59:00Z").interval == 12 and g("2026-10-25T02:00:00Z").interval == 21
    last, nxt = g("2026-10-25T21:45:00Z"), g("2026-10-25T22:00:00Z")
    assert (last.interval, last.interval_opcom, last.attributes["data_azi"]) == (100, 96, "2026-10-25")
    assert (nxt.interval, nxt.interval_opcom, nxt.attributes["data_azi"]) == (1, 97, "2026-10-26")
    # 24.10: mâine = 100 sloturi
    c = g("2026-10-24T08:00:00Z").attributes
    assert len(c["maine_15"]) == 100 and len(c["maine_60"]) == 25
    contiguous(c["maine_start_utc"])


def test_92_slot_day_2027():
    pr = fill(["2027-03-26", "2027-03-27", "2027-03-28", "2027-03-29", "2027-03-30"])
    assert len(pr["2027-03-28"]) == 92
    a = p.build_snapshot(pr, utc("2027-03-28T10:00:00Z"), RO).attributes
    assert [len(a[k]) for k in ("azi_15", "azi_30", "azi_60")] == [92, 46, 23]
    assert a["azi_start_utc"][0] == "2027-03-27T22:00Z" and a["azi_start_utc"][91] == "2027-03-28T20:45Z"
    contiguous(a["azi_start_utc"])
    assert None not in a["azi_15"]
    b = p.build_snapshot(pr, utc("2027-03-29T10:00:00Z"), RO).attributes
    assert len(b["azi_15"]) == 96 and b["azi_start_utc"][0] == "2027-03-28T21:00Z"
    assert b["azi_15"][:4] == [pr["2027-03-28"][i] for i in (89, 90, 91, 92)]
    x = p.build_snapshot(pr, utc("2027-03-28T00:59:00Z"), RO)
    y = p.build_snapshot(pr, utc("2027-03-28T01:00:00Z"), RO)
    assert y.interval - x.interval == 1 and y.interval == 13


# ---- referință aritmetică (portul exact din opcom-core.js) față de zoneinfo
def last_sunday(y, m):
    nxt = datetime(y + (m == 12), m % 12 + 1, 1, tzinfo=UTC)
    last = nxt - timedelta(days=1)
    return last.day - (last.weekday() + 1) % 7


def summer(t):
    y = t.year
    return datetime(y, 3, last_sunday(y, 3), 1, tzinfo=UTC) <= t < datetime(y, 10, last_sunday(y, 10), 1, tzinfo=UTC)


def ref_start_cet(key):
    u = datetime.fromisoformat(key).replace(tzinfo=UTC)
    return u - timedelta(hours=2 if summer(u - timedelta(hours=1)) else 1)


def ref_start_ro(key):
    u = datetime.fromisoformat(key).replace(tzinfo=UTC)
    return u - timedelta(hours=3 if summer(u - timedelta(hours=2)) else 2)


def test_zoneinfo_matches_arithmetic_rule_2026_2027():
    k = "2026-01-01"
    while k <= "2027-12-31":
        assert p.opcom_day_start(k) == ref_start_cet(k), k
        assert p.local_day_start(k, RO) == ref_start_ro(k), k
        k = p.key_plus(k, 1)


def test_full_years_all_days_complete():
    store = fill([p.key_plus("2025-12-31", i) for i in range(0, 735)])
    n23 = n25 = 0
    k = "2026-01-01"
    while k <= "2027-12-31":
        now = p.local_day_start(k, RO) + timedelta(hours=7, minutes=10)
        a = p.build_snapshot(store, now, RO).attributes
        n = p.slots_in_local_day(k, RO)
        assert len(a["azi_15"]) == n and None not in a["azi_15"] and None not in a["maine_15"]
        contiguous(a["azi_start_utc"])
        for s, v in zip(a["azi_start_utc"], a["azi_15"]):
            assert v == pret(utc(s))
        n23 += n == 92
        n25 += n == 100
        k = p.key_plus(k, 1)
    assert (n23, n25) == (2, 2)


def test_classify_and_days():
    assert p.classify_response(200, csv("22-10-2026_15.csv")) == "ok"
    assert p.classify_response(200, "") == "empty"
    assert p.classify_response(200, '"PIP si volum tranzactionat pentru ziua de livrare: 24/10/2026"\n\n') == "empty"
    assert p.classify_response(200, "<html><body>Blocked</body></html>") == "blocked"
    assert p.classify_response(403, "") == "blocked"
    assert p.classify_response(200, "<html>ceva</html>") == "not_csv"
    assert p.classify_response(500, "eroare") == "http_error"
    assert p.days_to_fetch(utc("2026-10-22T05:00:00Z"), RO) == ["2026-10-21", "2026-10-22"]
    assert p.days_to_fetch(utc("2026-10-22T11:00:00Z"), RO) == ["2026-10-21", "2026-10-22", "2026-10-23"]
    assert p.days_to_fetch(utc("2026-10-21T21:30:00Z"), RO) == ["2026-10-21", "2026-10-22"]
    assert p.day_url("2026-10-22").endswith("/22/10/2026/ro?resolution=15")


def test_next_cheap_hour(prices, snap):
    f = p.next_cheap_hour(snap, utc("2026-10-22T18:30:00Z"))
    # după 21:30 local: 22:00 (1527.9) sau 23:00 sunt peste medie? media zilei ~1340 -> nimic azi, mâine gol
    assert f is None
    f = p.next_cheap_hour(snap, utc("2026-10-22T00:00:00Z"))
    assert f is not None and f[0] > utc("2026-10-22T00:00:00Z") and f[2] < f[3]


def test_json_roundtrip(prices):
    assert p.prices_from_json(p.prices_to_json(prices)) == prices
