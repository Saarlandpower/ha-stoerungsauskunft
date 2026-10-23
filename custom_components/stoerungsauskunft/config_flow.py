"""Config- und Options-Flow."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
)

from .api import StoerungsauskunftApi, StoerungsauskunftError
from .const import (
    AREA_CUSTOM,
    AREA_SAARLAND,
    CONF_AREA,
    CONF_MIN_ADDRESSES,
    CONF_MIN_REPORTS,
    CONF_POSTAL_CODES,
    CONF_QUIET,
    CONF_SCAN_INTERVAL,
    CONF_SECTORS,
    CONF_WINDOW,
    DEFAULT_MIN_ADDRESSES,
    DEFAULT_MIN_REPORTS,
    DEFAULT_QUIET,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SECTORS,
    DEFAULT_WINDOW,
    DOMAIN,
    MIN_SCAN_INTERVAL,
    SECTORS,
)
from .model import parse_codes

SECTOR_SELECTOR = SelectSelector(
    SelectSelectorConfig(
        options=[SelectOptionDict(value=str(k), label=v["name"]) for k, v in SECTORS.items()],
        multiple=True,
        mode=SelectSelectorMode.LIST,
    )
)
AREA_SELECTOR = SelectSelector(
    SelectSelectorConfig(
        options=[AREA_SAARLAND, AREA_CUSTOM],
        translation_key="area",
        mode=SelectSelectorMode.LIST,
    )
)


def _number(minimum: int, maximum: int, unit: str | None = None) -> NumberSelector:
    config = NumberSelectorConfig(min=minimum, max=maximum, step=1, mode=NumberSelectorMode.BOX)
    if unit:
        config["unit_of_measurement"] = unit
    return NumberSelector(config)


def _area_schema(defaults: dict[str, Any]) -> dict:
    return {
        vol.Required(CONF_AREA, default=defaults.get(CONF_AREA, AREA_SAARLAND)): AREA_SELECTOR,
        vol.Optional(CONF_POSTAL_CODES, default=defaults.get(CONF_POSTAL_CODES, "")): TextSelector(),
        vol.Required(CONF_SECTORS, default=defaults.get(CONF_SECTORS, DEFAULT_SECTORS)): SECTOR_SELECTOR,
    }


def _validate_area(data: dict[str, Any]) -> dict[str, str]:
    errors: dict[str, str] = {}
    if data[CONF_AREA] == AREA_CUSTOM and not parse_codes(data.get(CONF_POSTAL_CODES, "")):
        errors[CONF_POSTAL_CODES] = "no_postal_codes"
    if not data.get(CONF_SECTORS):
        errors[CONF_SECTORS] = "no_sectors"
    return errors


def _normalize(data: dict[str, Any]) -> dict[str, Any]:
    out = dict(data)
    out[CONF_POSTAL_CODES] = ", ".join(parse_codes(data.get(CONF_POSTAL_CODES, "")))
    return out


class StoerungsauskunftConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = _validate_area(user_input)
            if not errors:
                data = _normalize(user_input)
                area_id = (AREA_SAARLAND if data[CONF_AREA] == AREA_SAARLAND
                           else ",".join(sorted(parse_codes(data[CONF_POSTAL_CODES]))))
                await self.async_set_unique_id(area_id)
                self._abort_if_unique_id_configured()
                try:
                    await StoerungsauskunftApi(async_get_clientsession(self.hass)).discover_token()
                except StoerungsauskunftError:
                    errors["base"] = "cannot_connect"
                else:
                    title = data.pop(CONF_NAME, None) or (
                        "Saarland" if data[CONF_AREA] == AREA_SAARLAND else data[CONF_POSTAL_CODES])
                    return self.async_create_entry(title=title, data=data)

        defaults = user_input or {}
        schema = vol.Schema({
            vol.Optional(CONF_NAME, default=defaults.get(CONF_NAME, "")): TextSelector(),
            **_area_schema(defaults),
        })
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return StoerungsauskunftOptionsFlow()


class StoerungsauskunftOptionsFlow(OptionsFlow):
    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = _validate_area(user_input)
            if not errors:
                return self.async_create_entry(data=_normalize(user_input))

        current = {**self.config_entry.data, **self.config_entry.options, **(user_input or {})}
        schema = vol.Schema({
            **_area_schema(current),
            vol.Required(CONF_SCAN_INTERVAL, default=current.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)):
                _number(MIN_SCAN_INTERVAL, 60, "min"),
            vol.Required(CONF_WINDOW, default=current.get(CONF_WINDOW, DEFAULT_WINDOW)): _number(5, 240, "min"),
            vol.Required(CONF_MIN_REPORTS, default=current.get(CONF_MIN_REPORTS, DEFAULT_MIN_REPORTS)): _number(1, 100),
            vol.Required(CONF_MIN_ADDRESSES,
                         default=current.get(CONF_MIN_ADDRESSES, DEFAULT_MIN_ADDRESSES)): _number(1, 100),
            vol.Required(CONF_QUIET, default=current.get(CONF_QUIET, DEFAULT_QUIET)): _number(15, 1440, "min"),
        })
        return self.async_show_form(step_id="init", data_schema=schema, errors=errors)
