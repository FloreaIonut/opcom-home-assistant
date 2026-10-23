"""Client HTTP pentru CSV-ul public OPCOM PZU."""

from __future__ import annotations

import logging

import aiohttp

from .const import BODY_SNIPPET, HEADER_PROFILES, REQUEST_TIMEOUT
from .parser import classify_response, day_url, parse_csv

_LOGGER = logging.getLogger(__name__)


class OpcomError(Exception):
    """Eroare de bază."""

    code = "cannot_connect"


class OpcomConnectError(OpcomError):
    """Rețea, timeout sau HTTP != 200."""

    code = "cannot_connect"


class OpcomBlockedError(OpcomError):
    """WAF / pagină „Blocked" / 403."""

    code = "blocked"


class OpcomNotCsvError(OpcomError):
    """200, dar răspunsul nu e CSV (HTML intermitent)."""

    code = "blocked"


class OpcomClient:
    def __init__(self, session: aiohttp.ClientSession, zone: str = "Romania") -> None:
        self._session = session
        self._zone = zone
        self._good = 0      # indexul profilului de antete care a mers ultima dată

    async def fetch_day(self, key: str, attempt: int = 0) -> dict[int, float] | None:
        """{interval: preț} pentru ziua OPCOM `key`; None dacă ziua nu e publicată încă.

        `attempt` > 0 = reîncercare după blocare: se folosește următorul profil de antete.
        """
        idx = (self._good + attempt) % len(HEADER_PROFILES)
        profile, headers = HEADER_PROFILES[idx]
        url = day_url(key)
        timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
        try:
            async with self._session.get(
                url, headers=headers, timeout=timeout, allow_redirects=True
            ) as resp:
                raw = await resp.read()
                status = resp.status
        except TimeoutError as err:
            raise OpcomConnectError(f"Timeout la {key}") from err
        except aiohttp.ClientError as err:
            raise OpcomConnectError(f"Eroare de rețea la {key}: {err}") from err
        text = raw.decode("utf-8", errors="replace")
        kind = classify_response(status, text, self._zone)
        _LOGGER.debug("GET %s [%s] -> HTTP %s, %d octeți, %s", key, profile, status, len(raw), kind)
        if kind in ("ok", "empty"):
            self._good = idx
        if kind == "ok":
            return parse_csv(text, self._zone)
        if kind == "empty":
            return None
        if kind == "blocked":
            snippet = " ".join(text[:BODY_SNIPPET].split())
            raise OpcomBlockedError(
                f"OPCOM a blocat cererea pentru {key} (HTTP {status}, antete {profile}): "
                f"probabil WAF; corp: {snippet!r}"
            )
        if kind == "not_csv":
            raise OpcomNotCsvError(f"Răspunsul pentru {key} nu este CSV (HTTP {status})")
        raise OpcomConnectError(f"HTTP {status} pentru {key}")
