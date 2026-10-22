# Corecția fusului orar OPCOM (v1.1.0)

## Problema
Intervalele OPCOM PZU sunt în **CET/CEST** (ora României minus 1 h), nu în ora României. Conform procedurii OPCOM pentru PZU (v8, 10.07.2026), intervalul 1 este 00:00–00:15 CET/CEST, adică **01:00–01:15 ora României**. Versiunea 1.0 lua `ora = (interval-1)*15` și intervalul curent din ceasul României, deci starea senzorului și listele `azi_*`/`maine_*` erau decalate cu 1 h (4 sloturi).

## Logica nouă
- La salvare, fiecare slot primește `ts_utc` (început de slot, UTC) = 00:00 CET/CEST al zilei OPCOM + `(interval-1)*15 min`. Se păstrează `interval` și `ora_cet`.
- „Azi” și „mâine” sunt zile locale `Europe/Bucharest`, calculate din `ts_utc`. Ziua locală începe cu sloturile 93–96 ale zilei OPCOM de ieri și se termină cu sloturile 1–92 ale zilei de azi. De aceea se cere și ziua de ieri.
- Numărul de sloturi urmează ziua reală: **96** în mod normal, **92** (23 h) la trecerea la ora de vară, **100** (25 h) la trecerea la ora de iarnă.
- Calculul orei de vară/iarnă este aritmetic (regula UE: ultima duminică din martie/octombrie, 01:00 UTC), fără `Intl`, deci la fel în orice versiune de Node.
- `interval` = poziția în ziua locală (1-based); `interval_opcom` = intervalul OPCOM (ca pe opcom.ro).
- Se păstrează ultimele 5 zile în `opcom_preturi`. Datele vechi (fără `ts_utc`) se citesc în continuare.

## Atribute noi
`azi_start_utc`, `maine_start_utc` (început de slot de 15 min, ISO UTC, ex. `2026-10-21T21:00Z`) și `interval_opcom`. Celelalte atribute rămân la fel. Dacă lipsește ieri, primele sloturi sunt `null` (listele rămân aliniate).

## Cardul
- Zile de 24 h: `azi_60[h]` este acum ora locală `h:00–h+1:00`, deci cardul din v1.0 rămâne corect.
- Zile de 23/25 h: indexarea din ceas nu mai e corectă. Cardul din acest repo folosește acum `azi_start_utc` / `maine_start_utc` pentru etichete și pentru intervalul curent. Fără aceste atribute revine la calculul vechi.
- Limită: în ziua de 25 h ora 03:00 apare de două ori (EEST și EET), iar prima este afișată ca „03:00–03:00”. Axa de sub grafic are repere fixe 00/06/12/18/24, aproximative în zilele de 23/25 h.
- Cardul tău propriu: folosește `*_start_utc` pentru etichete (`new Date(iso).toLocaleTimeString('ro-RO', {timeZone: 'Europe/Bucharest'})`) și caută slotul curent după `Date.now()`, nu după ora din ceas.

## Testare
`node tests/run-tests.js` (offline). Folosește CSV-uri reale OPCOM (`tests/date/`, publice) și date sintetice pentru 25.10.2026 (100 sloturi) și 28.03.2027 (92 sloturi), plus toate zilele din 2026–2027 comparate cu `Intl`.
