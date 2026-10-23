"""DataUpdateCoordinator für störungsauskunft.de."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import StoerungsauskunftApi, StoerungsauskunftError
from .const import (
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
    EVENT_OUTAGE_NEW,
    EVENT_OUTAGE_RESOLVED,
    EVENT_SUSPECTED,
    MIN_SCAN_INTERVAL,
    SAARLAND_PLZ,
    SECTORS,
)
from .model import TZ, AreaMatcher, SectorState, Settings, evaluate, parse_codes

_LOGGER = logging.getLogger(__name__)

type StoerungsConfigEntry = ConfigEntry[StoerungsCoordinator]


def entry_value(entry: ConfigEntry, key: str, default):
    """Optionen haben Vorrang vor den Daten aus der Ersteinrichtung."""
    return entry.options.get(key, entry.data.get(key, default))


class StoerungsCoordinator(DataUpdateCoordinator[dict[int, SectorState]]):
    """Holt alle paar Minuten Störungen und Meldungen und wertet sie aus."""

    config_entry: StoerungsConfigEntry

    def __init__(self, hass: HomeAssistant, entry: StoerungsConfigEntry) -> None:
        interval = max(MIN_SCAN_INTERVAL, int(entry_value(entry, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)))
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(minutes=interval),
        )
        self.api = StoerungsauskunftApi(async_get_clientsession(hass))
        self.sectors = [int(s) for s in entry_value(entry, CONF_SECTORS, DEFAULT_SECTORS) if int(s) in SECTORS]
        if entry_value(entry, CONF_AREA, AREA_SAARLAND) == AREA_SAARLAND:
            codes = list(SAARLAND_PLZ)
        else:
            codes = parse_codes(entry_value(entry, CONF_POSTAL_CODES, ""))
        self.match = AreaMatcher(codes)
        self.settings = Settings(
            window=int(entry_value(entry, CONF_WINDOW, DEFAULT_WINDOW)),
            min_reports=int(entry_value(entry, CONF_MIN_REPORTS, DEFAULT_MIN_REPORTS)),
            min_addresses=int(entry_value(entry, CONF_MIN_ADDRESSES, DEFAULT_MIN_ADDRESSES)),
            quiet=int(entry_value(entry, CONF_QUIET, DEFAULT_QUIET)),
        )
        self._known_outages: dict[str, dict] | None = None
        self._known_suspected: set[str] | None = None

    async def _async_update_data(self) -> dict[int, SectorState]:
        try:
            outages = await self.api.outages(self.sectors)
            reports = {s: await self.api.user_notifications(s) for s in self.sectors}
        except StoerungsauskunftError as err:
            raise UpdateFailed(str(err)) from err

        result = evaluate(outages, reports, self.sectors, self.match, self.settings, datetime.now(TZ))
        self._fire_events(result)
        return result

    def _fire_events(self, result: dict[int, SectorState]) -> None:
        """Ereignisse für Automationen. Beim ersten Abruf wird nur der Stand gemerkt."""
        outages_now: dict[str, dict] = {}
        suspected_now: dict[str, dict] = {}
        for sector, st in result.items():
            sector_key = SECTORS[sector]["key"]
            for o in st.outages:
                outages_now[f"{sector}|{o['id']}"] = {**o, "sector": sector_key}
            for a in st.areas:
                if a["suspected"]:
                    suspected_now[f"{sector}|{a['postal_code']}|{a['since']}"] = {**a, "sector": sector_key}

        base = {"config_entry_id": self.config_entry.entry_id}
        if self._known_outages is not None:
            for key, o in outages_now.items():
                if key not in self._known_outages:
                    self.hass.bus.async_fire(EVENT_OUTAGE_NEW, {**base, **o})
            for key, o in self._known_outages.items():
                if key not in outages_now:
                    self.hass.bus.async_fire(EVENT_OUTAGE_RESOLVED, {**base, **o})
        if self._known_suspected is not None:
            for key, a in suspected_now.items():
                if key not in self._known_suspected:
                    self.hass.bus.async_fire(EVENT_SUSPECTED, {**base, **a})
        self._known_outages = outages_now
        self._known_suspected = set(suspected_now)
