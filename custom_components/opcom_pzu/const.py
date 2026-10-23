"""Constante pentru integrarea OPCOM PZU."""

from __future__ import annotations

from datetime import timedelta

DOMAIN = "opcom_pzu"
NAME = "OPCOM PZU"

CONF_TIMEZONE = "timezone"
CONF_ZONE = "zone"
DEFAULT_TIMEZONE = "Europe/Bucharest"
DEFAULT_ZONE = "Romania"

# Intervalele OPCOM sunt în CET/CEST (Europe/Berlin = ora României minus 1 h).
OPCOM_TIMEZONE = "Europe/Berlin"

CSV_URL = "https://www.opcom.ro/rapoarte-pzu-raportPIP-export-csv/{dd}/{mm}/{yyyy}/ro?resolution=15"
REFERER = "https://www.opcom.ro/pp/pzu/rapoarte"
REQUEST_TIMEOUT = 30

# Profiluri de antete, în ordinea încercării (la blocare se trece la următorul; ultimul care a mers
# rămâne primul). Node-RED-ul care descarcă fără probleme NU trimite niciun antet propriu
# (doar cele implicite ale bibliotecii HTTP), fără Referer și fără Sec-Fetch-*. Un User-Agent de Chrome
# + Sec-Fetch-* trimise printr-o amprentă TLS/HTTP de non-browser (aiohttp) e un semnal clasic de
# „bot care se dă drept browser" pentru WAF (Barracuda), deci profilul „browser" e ultima soluție.
HEADER_PROFILES: tuple[tuple[str, dict[str, str]], ...] = (
    ("nodered", {
        "User-Agent": "got (https://github.com/sindresorhus/got)",
        "Accept-Encoding": "gzip, deflate, br",
    }),
    ("minimal", {
        "User-Agent": "Mozilla/5.0",
        "Accept": "text/csv,*/*",
        "Accept-Language": "ro-RO,ro;q=0.9,en;q=0.8",
    }),
    ("browser", {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
        ),
        "Accept": "text/csv,text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ro-RO,ro;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": REFERER,
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin",
        "Upgrade-Insecure-Requests": "1",
    }),
)

# Cât de des „se uită” coordinatorul dacă mai are ceva de descărcat (fără rețea dacă nu are).
UPDATE_INTERVAL = timedelta(minutes=10)
# Prețurile de mâine se cer după această oră locală (13:00 CET = 14:00 ora României),
# apoi la fiecare TOMORROW_RETRY până apar.
TOMORROW_HOUR = 14
TOMORROW_RETRY = timedelta(minutes=30)
# Încercări la blocare WAF / răspuns care nu e CSV, cu pauză (secunde) între ele.
FETCH_ATTEMPTS = 3
RETRY_PAUSE = (5.0, 15.0)
# Pauză (secunde, cu jitter) între cererile pentru zile diferite, ca să nu fie rafală.
DAY_PAUSE = (5.0, 10.0)
# După o rundă blocată, următoarea încercare peste 1 min, 5 min, apoi 15 min (rămâne 15 min).
BLOCK_BACKOFF = (timedelta(minutes=1), timedelta(minutes=5), timedelta(minutes=15))
# Lungimea fragmentului din corpul răspunsului care apare în log la blocare.
BODY_SNIPPET = 200
# Câte zile OPCOM se păstrează în cache.
KEEP_DAYS = 6

STORAGE_VERSION = 1
STORAGE_KEY_PREFIX = f"{DOMAIN}.prices."
