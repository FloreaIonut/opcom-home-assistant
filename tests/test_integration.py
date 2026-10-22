"""Teste cu Home Assistant real (pytest-homeassistant-custom-component), offline.

Clientul HTTP e înlocuit cu CSV-urile reale din tests/fixtures.
"""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

import pytest
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.opcom_pzu import coordinator as coord_mod
from custom_components.opcom_pzu import parser as p
from custom_components.opcom_pzu.api import OpcomBlockedError, OpcomClient, OpcomNotCsvError
from custom_components.opcom_pzu.const import DOMAIN

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")

_REAL_FETCH = OpcomClient.fetch_day   # metoda reală, înainte de înlocuirea din fixture

FIX = Path(__file__).resolve().parent / "fixtures"
FILES = {
    "2026-10-21": "21-10-2026_15.csv",
    "2026-10-22": "22-10-2026_15.csv",
    "2026-10-23": "23-10-2026_15.csv",
}


class Fake:
    """Înlocuiește OpcomClient.fetch_day."""

    calls: list[str] = []
    mode = "ok"          # ok | blocked | notcsv | down
    published = set(FILES)

    @classmethod
    def reset(cls):
        cls.calls = []
        cls.mode = "ok"
        cls.published = set(FILES)

    async def fetch_day(self, key):
        Fake.calls.append(key)
        if Fake.mode == "blocked":
            raise OpcomBlockedError("test WAF")
        if Fake.mode == "notcsv":
            raise OpcomNotCsvError("test html")
        if key not in Fake.published or key not in FILES:
            return None
        return p.parse_csv((FIX / FILES[key]).read_text(encoding="utf-8"))


@pytest.fixture(autouse=True)
def _fake(monkeypatch):
    Fake.reset()
    monkeypatch.setattr(coord_mod.OpcomClient, "fetch_day", Fake.fetch_day)
    async def nopause(_b):
        return None
    monkeypatch.setattr(coord_mod, "_pause", nopause)
    # fără sesiune aiohttp reală (ar porni firul DNS pycares)
    monkeypatch.setattr(coord_mod, "async_get_clientsession", lambda hass: None)
    from custom_components.opcom_pzu import config_flow as cf
    monkeypatch.setattr(cf, "async_get_clientsession", lambda hass: None)


async def _setup(hass):
    entry = MockConfigEntry(domain=DOMAIN, data={"timezone": "Europe/Bucharest", "zone": "Romania"})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


@pytest.mark.freeze_time("2026-10-22 18:30:00")   # 21:30 EEST
async def test_entities_and_values(hass, hass_storage):
    await _setup(hass)
    st = hass.states.get("sensor.opcom_pzu_pret_acum")
    assert st is not None and float(st.state) == 1638.94
    a = st.attributes
    assert a["interval_opcom"] == 83 and a["interval"] == 87
    assert a["azi_60"][21] == 1532.03 and a["azi_60"][5] == 968.94 and a["azi_60"][0] == 1295.10
    assert a["maine_disponibil"] is True and len(a["maine_60"]) == 24     # 23.10 real, după 14:00
    assert a["unit_of_measurement"] == "lei/MWh"
    assert float(hass.states.get("sensor.opcom_pzu_pret_acum_kwh").state) == 1.63894
    assert float(hass.states.get("sensor.opcom_pzu_minim_azi").state) == min(
        v for v in a["azi_15"] if v is not None
    )
    assert float(hass.states.get("sensor.opcom_pzu_maxim_azi").state) == a["azi"]["max"]
    assert float(hass.states.get("sensor.opcom_pzu_medie_azi").state) == a["azi"]["medie"]
    # ora ieftină următoare: prima oră de mâine sub media lui (azi nu mai are după 21:30)
    ch = hass.states.get("sensor.opcom_pzu_ora_ieftina_urmatoare")
    assert ch.state not in ("unknown", "unavailable")
    # nu s-a creat senzorul Node-RED/MQTT
    assert hass.states.get("sensor.opcom_pret_acum") is None
    # entity_id explicite
    reg = er.async_get(hass)
    ids = {e.entity_id for e in reg.entities.values() if e.platform == DOMAIN}
    assert ids == {f"sensor.opcom_pzu_{k}" for k in
                   ("pret_acum", "pret_acum_kwh", "minim_azi", "maxim_azi", "medie_azi", "ora_ieftina_urmatoare")}
    # Store scris
    key = next(k for k in hass_storage if k.startswith("opcom_pzu.prices."))
    assert set(hass_storage[key]["data"]["prices"]) == set(FILES)


@pytest.mark.freeze_time("2026-10-22 18:30:00")
async def test_unrecorded_attributes(hass):
    await _setup(hass)
    from custom_components.opcom_pzu.sensor import PriceNow
    for k in ("azi_15", "azi_60", "maine_15", "azi_start_utc", "maine_start_utc"):
        assert k in PriceNow._unrecorded_attributes


@pytest.mark.freeze_time("2026-10-22 18:30:00")
async def test_quarter_hour_tick_without_download(hass, freezer):
    await _setup(hass)
    n = len(Fake.calls)
    s0 = hass.states.get("sensor.opcom_pzu_pret_acum")
    freezer.move_to("2026-10-22 18:45:00")
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    s1 = hass.states.get("sensor.opcom_pzu_pret_acum")
    assert len(Fake.calls) == n                               # fără re-descărcare
    assert float(s1.state) != float(s0.state) and s1.attributes["interval_opcom"] == 84
    assert s1.attributes["interval"] == 88


@pytest.mark.freeze_time("2026-10-22 18:30:00")
async def test_midnight_rollover_uses_cache(hass, freezer):
    await _setup(hass)
    freezer.move_to("2026-10-22 21:00:00")                    # 00:00 EEST 23.10
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    a = hass.states.get("sensor.opcom_pzu_pret_acum").attributes
    assert a["data_azi"] == "2026-10-23" and a["interval"] == 1 and a["interval_opcom"] == 93
    assert a["maine_disponibil"] is False


@pytest.mark.freeze_time("2026-10-22 08:00:00")           # 11:00 EEST, mâine încă nu se cere
async def test_tomorrow_not_requested_before_14(hass):
    await _setup(hass)
    assert sorted(set(Fake.calls)) == ["2026-10-21", "2026-10-22"]
    assert hass.states.get("sensor.opcom_pzu_pret_acum").attributes["maine_disponibil"] is False


@pytest.mark.freeze_time("2026-10-22 11:05:00")           # 14:05 EEST
async def test_tomorrow_retry_every_30min_then_stop(hass, freezer):
    Fake.published = {"2026-10-21", "2026-10-22"}
    await _setup(hass)
    assert Fake.calls.count("2026-10-23") == 1
    # +10 min: nu cere din nou mâine (pauză 30 min), nici ieri/azi (complete)
    freezer.tick(timedelta(minutes=10))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    assert Fake.calls.count("2026-10-23") == 1
    # +30 min: reîncearcă; acum e publicat
    Fake.published = set(FILES)
    freezer.tick(timedelta(minutes=30))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    assert Fake.calls.count("2026-10-23") == 2
    assert hass.states.get("sensor.opcom_pzu_pret_acum").attributes["maine_disponibil"] is True
    # apoi nu mai cere nimic
    n = len(Fake.calls)
    for _ in range(4):
        freezer.tick(timedelta(minutes=15))
        async_fire_time_changed(hass, dt_util.utcnow())
        await hass.async_block_till_done()
    assert len(Fake.calls) == n


@pytest.mark.freeze_time("2026-10-22 18:30:00")
async def test_dedup_store_not_rewritten_if_unchanged(hass, hass_storage):
    entry = await _setup(hass)
    c = entry.runtime_data
    saves = []
    orig = c._store.async_save

    async def spy(data):
        saves.append(1)
        await orig(data)

    c._store.async_save = spy
    c.prices["2026-10-22"] = dict(c.prices["2026-10-22"])
    c.prices.pop("2026-10-21")                                # lipsește -> se cere din nou, dar...
    await c.async_refresh()
    assert len(saves) == 1                                    # ieri revenit = schimbare reală
    await c.async_refresh()
    assert len(saves) == 1                                    # acum complet: nicio rescriere


@pytest.mark.freeze_time("2026-10-22 18:30:00")
async def test_store_restores_after_restart_while_blocked(hass, hass_storage):
    await _setup(hass)
    key = next(k for k in hass_storage if k.startswith("opcom_pzu.prices."))
    saved = hass_storage[key]
    await hass.config_entries.async_unload(hass.config_entries.async_entries(DOMAIN)[0].entry_id)
    await hass.config_entries.async_remove(hass.config_entries.async_entries(DOMAIN)[0].entry_id)
    await hass.async_block_till_done()
    # repornire cu OPCOM blocat dar cu cache existent (același entry_id)
    Fake.reset()
    Fake.mode = "blocked"
    entry = MockConfigEntry(domain=DOMAIN, data={"timezone": "Europe/Bucharest", "zone": "Romania"}, entry_id="cache1")
    hass_storage["opcom_pzu.prices.cache1"] = saved
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    st = hass.states.get("sensor.opcom_pzu_pret_acum")
    assert st.state not in ("unavailable", "unknown") and float(st.state) == 1638.94


@pytest.mark.freeze_time("2026-10-22 18:30:00")
async def test_blocked_without_cache_is_unavailable_and_logged(hass, caplog):
    Fake.mode = "blocked"
    await _setup(hass)
    assert hass.states.get("sensor.opcom_pzu_pret_acum").state == "unavailable"
    assert "blocked" in caplog.text and "descărcare eșuată" in caplog.text
    # retry cu pauză: 3 încercări / zi cerută, pentru ieri
    assert Fake.calls.count("2026-10-21") == 3


@pytest.mark.freeze_time("2026-10-22 18:30:00")
async def test_not_csv_retries_and_recovers(hass, freezer):
    Fake.mode = "notcsv"
    await _setup(hass)
    assert hass.states.get("sensor.opcom_pzu_pret_acum").state == "unavailable"
    Fake.mode = "ok"
    freezer.tick(timedelta(minutes=10))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    assert float(hass.states.get("sensor.opcom_pzu_pret_acum").state) == 1638.94


@pytest.mark.freeze_time("2026-10-22 18:30:00")
async def test_log_error_deduplicated(hass, caplog):
    Fake.mode = "blocked"
    entry = await _setup(hass)
    c = entry.runtime_data
    n = caplog.text.count("descărcare eșuată")
    c._next_try.clear()
    await c.async_refresh()
    assert caplog.text.count("descărcare eșuată") == n        # același mesaj: doar la debug


async def test_config_flow(hass):
    with patch.object(coord_mod.OpcomClient, "fetch_day", Fake.fetch_day), patch(
        "custom_components.opcom_pzu.config_flow.OpcomClient.fetch_day", Fake.fetch_day
    ):
        r = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
        assert r["type"] == "form" and r["step_id"] == "user"
        r = await hass.config_entries.flow.async_configure(
            r["flow_id"], {"timezone": "Europe/Nowhere", "zone": "Romania"}
        )
        assert r["errors"] == {"base": "invalid_timezone"}
        Fake.published = set()
        r = await hass.config_entries.flow.async_configure(
            r["flow_id"], {"timezone": "Europe/Bucharest", "zone": "Romania"}
        )
        assert r["errors"] == {"base": "no_data"}
        Fake.mode = "blocked"
        r = await hass.config_entries.flow.async_configure(
            r["flow_id"], {"timezone": "Europe/Bucharest", "zone": "Romania"}
        )
        assert r["errors"] == {"base": "blocked"}


async def test_config_flow_ok_and_single_instance(hass):
    Fake.published = set(FILES)
    with patch("custom_components.opcom_pzu.config_flow.OpcomClient.fetch_day", Fake.fetch_day), patch.object(
        coord_mod.OpcomClient, "fetch_day", Fake.fetch_day
    ):
        with patch("custom_components.opcom_pzu.config_flow.local_key", return_value="2026-10-22"):
            r = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
            r = await hass.config_entries.flow.async_configure(
                r["flow_id"], {"timezone": "Europe/Bucharest", "zone": "Romania"}
            )
        assert r["type"] == "create_entry" and r["data"] == {"timezone": "Europe/Bucharest", "zone": "Romania"}
        await hass.async_block_till_done()
        r2 = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
        assert r2["type"] == "abort" and r2["reason"] == "already_configured"


class _Resp:
    def __init__(self, status, body):
        self.status, self._b = status, body.encode()
    async def read(self):
        return self._b
    async def __aenter__(self):
        return self
    async def __aexit__(self, *a):
        return False


class _Sess:
    def __init__(self, status, body):
        self.r = (status, body)
        self.headers = None
    def get(self, url, headers=None, **kw):
        self.headers = headers
        self.url = url
        return _Resp(*self.r)


async def test_client_http_classification():
    csvt = (FIX / FILES["2026-10-22"]).read_text(encoding="utf-8")
    s = _Sess(200, csvt)
    rows = await _REAL_FETCH(OpcomClient(s), "2026-10-22")
    assert len(rows) == 96 and s.url.endswith("/22/10/2026/ro?resolution=15") and "Sec-Fetch-Mode" in s.headers
    assert await _REAL_FETCH(OpcomClient(_Sess(200, "")), "2026-10-24") is None
    with pytest.raises(OpcomBlockedError):
        await _REAL_FETCH(OpcomClient(_Sess(200, "<html>Request Rejected</html>")), "2026-10-22")
    with pytest.raises(OpcomBlockedError):
        await _REAL_FETCH(OpcomClient(_Sess(403, "Blocked")), "2026-10-22")
    with pytest.raises(OpcomNotCsvError):
        await _REAL_FETCH(OpcomClient(_Sess(200, "<html>x</html>")), "2026-10-22")

