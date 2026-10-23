# Changelog

## 0.1.1 (23.10.2026)
- Integrarea `opcom_pzu`: 3 profiluri de antete HTTP încercate pe rând, sesiune proprie, cereri făcute pe rând (nu în paralel), reîncercări cu pauză (backoff) la HTTP 403 / WAF, log de diagnostic pentru blocări.
- Limită cunoscută: după o cerere blocată, zilele următoare nu se mai cer în runda respectivă; vezi README, „Blocare WAF”.
- Teste: 33 (parser + integrare).

## 0.1.2 (23.10.2026)
- Card interactiv `card-opcom.yaml` (button-card + browser_mod): click pe card => fereastră cu graficul pe 60 min și prețul sub fiecare coloană; click pe coloană => detaliu pe 15 min; AZI / MÂINE / ORA CURENTĂ; fără helperi; corect în zile de 23/25 h; sloturile fără preț apar ca „–”.
- Nou `docs/card-preview.png` (date publice OPCOM). Doar card și documentație; codul integrării nu s-a schimbat.
- `nodered/card/card_opcom_interactiv.yaml`: același card interactiv pentru varianta Node-RED (`sensor.opcom_pret_acum`).

## 0.1.0 (22.10.2026)
- Prima versiune a integrării native `opcom_pzu` (fără Node-RED): senzori pentru prețul curent (lei/MWh și RON/kWh), minim/maxim/medie azi, următoarea oră ieftină; atribute 15/30/60 min pentru azi și mâine; cache; card `card-opcom.yaml`.
- Varianta Node-RED (fostul conținut al repo-ului, v1.1.0) mutată în `nodered/`; vezi [nodered/CHANGELOG.md](nodered/CHANGELOG.md).
