# Changelog

## 1.1.0 (22.10.2026)
- Corecție fus orar: intervalele OPCOM sunt în CET/CEST (ora României − 1 h). Vezi `docs/corectie-fus-orar.md`.
- `ts_utc` pe fiecare slot, zile locale `Europe/Bucharest`, 92/96/100 sloturi pe zi (zile de 23/25 h).
- Atribute noi: `interval_opcom`, `azi_start_utc`, `maine_start_utc`; `interval` = poziția în ziua locală.
- Se cere și ziua de ieri (sloturile 93–96 sunt 00:00–01:00 ora României); se păstrează 5 zile.
- Card: etichete și interval curent după `*_start_utc`.
- Teste offline (`tests/`); `build.py` păstrează ID-urile nodurilor.

## 1.0.0
- Prima versiune: flux Node-RED + card.
