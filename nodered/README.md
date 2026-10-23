# Prețuri energie OPCOM (PZU) în Home Assistant: varianta Node-RED

> Pentru instalări noi folosește [integrarea nativă din rădăcina repo-ului](../README.md) (fără Node-RED). Acest folder rămâne pentru cine folosește deja fluxul. Comenzile de aici (`python3 build.py`, `node tests/run-tests.js`) se rulează din folderul `nodered/`.

Flux **Node-RED** care descarcă prețurile pieței pentru ziua următoare (PZU) de pe [opcom.ro](https://www.opcom.ro) și le trimite în **Home Assistant**. Repo-ul include și un **card** pentru dashboard.

![card](preview.png)

- prețuri pe **15, 30 și 60 de minute**, pentru **azi** și **mâine** (mâine: după ce le publică OPCOM, în jur de 13:00–14:30);
- prețul pe ora curentă (ca pe opcom.ro la „60min”) și pe intervalul de 15 min, plus min / medie / max;
- grafic colorat: verde = ieftin, turcoaz = mediu, portocaliu = scump (treimi ale zilei); cele mai ieftine intervale rămase.

Node-RED poate rula oriunde: pe calculator, pe un Raspberry Pi sau ca add-on. Fluxul folosește **doar nodurile de bază** din Node-RED, fără pachete suplimentare și fără MQTT.

> **v1.1.0 (22.10.2026): corecție de fus orar.** Intervalele OPCOM sunt în **CET/CEST**, adică ora României minus 1 h (procedura OPCOM pentru PZU, v8, 10.07.2026: intervalul 1 = 00:00–00:15 CET = 01:00–01:15 ora României). Până la v1.0 prețurile erau decalate cu 1 h. Detalii: [docs/corectie-fus-orar.md](docs/corectie-fus-orar.md), [CHANGELOG.md](CHANGELOG.md). **Dacă ai instalat v1.0, reimportă fluxul** (vezi mai jos).

## Fișiere

| Fișier | Ce este |
|---|---|
| `flows/opcom-home-assistant.json` | fluxul Node-RED (Meniu → Import) |
| `card/card_opcom_preturi.yaml` | cardul pentru Home Assistant |
| `src/*.js`, `card/card_opcom.js`, `card/card_opcom.css`, `build.py` | sursele; `python3 build.py` reface fluxul și cardul (`src/opcom-core.js` e inserat în noduri) |
| `tests/run-tests.js`, `tests/date/` | teste offline (`node tests/run-tests.js`), cu CSV-uri reale OPCOM |
| `docs/corectie-fus-orar.md`, `CHANGELOG.md` | corecția de fus orar, istoric |

## Instalare

### 1. Token Home Assistant
În HA: **Profil** (jos, stânga) → **Securitate** → **Long-lived access tokens** → **Creează token**. Copiază tokenul.

### 2. Node-RED
1. Meniu → **Import** → lipește conținutul din `flows/opcom-home-assistant.json` → **Import**.
2. Deschide nodul **„Publică în HA”** și completează primele rânduri:
   ```js
   const HA_URL   = "http://192.168.1.10:8123";   // adresa ta de Home Assistant
   const HA_TOKEN = "eyJhbGciOi...";              // tokenul de la pasul 1
   ```
3. **Deploy**. După ~20 de secunde, sub noduri trebuie să apară:
   - „Salvează prețuri”: `AAAA-LL-ZZ: 96 intervale, …` (de 3 ori: ieri, azi, mâine, după ora 13);
   - „Rezultat HA”: verde **`HA OK la …`**.

   Dacă ai deja fluxul din v1.0: la import alege **„Replace existing nodes”** (nu „Import copy”, ar dubla nodurile; ID-urile sunt păstrate). Importul readuce placeholder-ul pentru `HA_URL`/`HA_TOKEN`, deci completează-le din nou. Nu trebuie resetat nimic: datele vechi se citesc, iar ziua de ieri se cere automat.

   Dacă vezi roșu `401`, tokenul e greșit. Altă eroare înseamnă că adresa HA e greșită sau HA nu răspunde.

### 3. Cardul
1. Instalează **[button-card](https://github.com/custom-cards/button-card)** (HACS → Frontend → „button-card”).
2. Dashboard → Edit → **Add card** → **Manual** → lipește conținutul din `card/card_opcom_preturi.yaml` → Save.

Fontul [Rajdhani](https://fonts.google.com/specimen/Rajdhani) e opțional; fără el cardul folosește fontul implicit.

**Card interactiv (opțional):** `card/card_opcom_interactiv.yaml` pe `sensor.opcom_pret_acum`: click pe card => fereastră cu graficul pe 60 min, click pe coloană => detaliu pe 15 min, AZI / MÂINE / ORA CURENTĂ. Cere și **[browser_mod](https://github.com/thomasloven/hass-browser_mod)** (HACS) pe lângă `button-card`; se lipește la fel, într-un card Manual. Nu cere helperi.

## Senzorul din Home Assistant

`sensor.opcom_pret_acum`: starea este prețul pe intervalul curent de 15 min (lei/MWh). Atribute:

| Atribut | Conținut |
|---|---|
| `azi_15`, `azi_30`, `azi_60` | prețurile de azi pe 15 min (96 valori) și mediile pe 30 min (48) și 60 min (24), în ordinea zilei **locale** (în zilele de 23/25 h: 92/100, 46/50, 23/25) |
| `maine_15`, `maine_30`, `maine_60` | la fel pentru mâine (goale până le publică OPCOM) |
| `azi`, `maine` | `{min, max, medie}` pe 15 min |
| `maine_disponibil` | `true` când există prețuri pentru mâine |
| `interval` | poziția intervalului curent în ziua locală (1–96; 1–92 / 1–100 în zilele de 23/25 h) |
| `interval_opcom` | numărul intervalului OPCOM curent (ca pe opcom.ro; la 21:30 ora României = 83, `interval` = 87) |
| `azi_start_utc`, `maine_start_utc` | începutul fiecărui slot de 15 min, ISO UTC (ex. `2026-10-21T21:00Z`), aliniat cu `azi_15`/`maine_15` |
| `data_azi`, `data_maine` | datele (ziua locală) |

Dacă lipsesc prețurile zilei de ieri, primele sloturi din `azi_*` sunt `null` (listele rămân aliniate).

Senzorul e creat prin API-ul REST al HA (`POST /api/states/sensor.opcom_pret_acum`), la fiecare minut. Nu poate fi editat din interfață (nu are `unique_id`). După un restart HA lipsește cel mult un minut. Istoricul se păstrează normal.

## Note

- OPCOM e întrebat doar când lipsesc prețurile: la pornire, apoi la 10 minute pentru ziua de mâine, după ora 13. Prețurile se țin în memoria fluxului; după un restart Node-RED se descarcă din nou.
- Orele afișate sunt în ora României (`Europe/Bucharest`). Intervalele OPCOM sunt în CET/CEST: intervalul 1 al zilei OPCOM = 01:00–01:15 ora României, iar sloturile 93–96 ale zilei OPCOM de ieri sunt 00:00–01:00 de azi. De aceea fluxul cere și ziua de ieri și păstrează ultimele 5 zile.
- Ziua locală are 96 de sloturi de 15 min, dar **92** în ziua trecerii la ora de vară (23 h) și **100** la ora de iarnă (25 h). În ziua de 25 h ora 03:00 apare de două ori.
- Cardul din acest repo folosește `*_start_utc` pentru etichete și intervalul curent, deci e corect și în zilele de 23/25 h (în ziua de 25 h prima oră 03:00 apare ca „03:00–03:00”; axa 00/06/12/18/24 e aproximativă). Un card propriu care indexează `azi_60[ora]` rămâne corect în zilele de 24 h; în cele de 23/25 h folosește `azi_start_utc`.
- Datele vin de la OPCOM S.A.; acest proiect nu este afiliat cu OPCOM.
