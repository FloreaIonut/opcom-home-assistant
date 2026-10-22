"""Config flow: un singur pas, fără credențiale."""

from __future__ import annotations

import logging
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import dt as dt_util

from .api import OpcomClient, OpcomError
from .const import CONF_TIMEZONE, CONF_ZONE, DEFAULT_TIMEZONE, DEFAULT_ZONE, DOMAIN, NAME
from .parser import local_key

_LOGGER = logging.getLogger(__name__)


def _schema(d: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_TIMEZONE, default=d.get(CONF_TIMEZONE, DEFAULT_TIMEZONE)): str,
            vol.Required(CONF_ZONE, default=d.get(CONF_ZONE, DEFAULT_ZONE)): str,
        }
    )


async def _validate(hass, tz_name: str, zone: str) -> str | None:
    """Cod de eroare sau None dacă CSV-ul de azi se descarcă."""
    try:
        tz = ZoneInfo(tz_name)
    except (ZoneInfoNotFoundError, ValueError):
        return "invalid_timezone"
    client = OpcomClient(async_get_clientsession(hass), zone)
    try:
        rows = await client.fetch_day(local_key(dt_util.utcnow(), tz))
    except OpcomError as err:
        _LOGGER.error("Validare: %s: %s", err.code, err)
        return err.code
    if not rows:
        _LOGGER.error("Validare: CSV-ul de azi nu are rânduri pentru zona %s", zone)
        return "no_data"
    return None


class OpcomConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()
        errors: dict[str, str] = {}
        if user_input is not None:
            err = await _validate(self.hass, user_input[CONF_TIMEZONE].strip(), user_input[CONF_ZONE].strip())
            if err is None:
                return self.async_create_entry(
                    title=NAME,
                    data={CONF_TIMEZONE: user_input[CONF_TIMEZONE].strip(), CONF_ZONE: user_input[CONF_ZONE].strip()},
                )
            errors["base"] = err
        return self.async_show_form(step_id="user", data_schema=_schema(user_input or {}), errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return OpcomOptionsFlow()


class OpcomOptionsFlow(OptionsFlow):
    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        current = {**self.config_entry.data, **self.config_entry.options}
        if user_input is not None:
            err = await _validate(self.hass, user_input[CONF_TIMEZONE].strip(), user_input[CONF_ZONE].strip())
            if err is None:
                return self.async_create_entry(
                    data={CONF_TIMEZONE: user_input[CONF_TIMEZONE].strip(), CONF_ZONE: user_input[CONF_ZONE].strip()}
                )
            errors["base"] = err
            current = {**current, **user_input}
        return self.async_show_form(step_id="init", data_schema=_schema(current), errors=errors)
