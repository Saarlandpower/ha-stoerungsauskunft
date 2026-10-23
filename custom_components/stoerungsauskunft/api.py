"""Client für die (inoffizielle) öffentliche API von störungsauskunft.de.

Die API gehört zum Web-Frontend und ist nicht dokumentiert. Der Basic-Auth-Wert
steht im öffentlichen JavaScript-Bundle der Website und wird von dort gelesen.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any

import aiohttp

from .const import API_BASE, SITE, USER_AGENT

_LOGGER = logging.getLogger(__name__)

_BUNDLE_RE = re.compile(r"(?:main|chunk)-[A-Za-z0-9]+\.js")
_TOKEN_RE = re.compile(r'basicAuth:"([^"]+)"')
_TIMEOUT = aiohttp.ClientTimeout(total=30)


class StoerungsauskunftError(Exception):
    """Allgemeiner Fehler beim Abruf."""


class StoerungsauskunftAuthError(StoerungsauskunftError):
    """Token konnte nicht ermittelt werden oder wird dauerhaft abgelehnt."""


class StoerungsauskunftApi:
    """Minimaler async-Client."""

    def __init__(self, session: aiohttp.ClientSession) -> None:
        self._session = session
        self._token: str | None = None
        self._lock = asyncio.Lock()

    async def _get_text(self, url: str) -> str:
        async with self._session.get(
            url, headers={"User-Agent": USER_AGENT}, timeout=_TIMEOUT
        ) as resp:
            resp.raise_for_status()
            return await resp.text()

    async def discover_token(self) -> str:
        """Basic-Auth-Wert aus dem Frontend-Bundle lesen."""
        try:
            index = await self._get_text(SITE)
            bundles = sorted(set(_BUNDLE_RE.findall(index)),
                             key=lambda n: not n.startswith("main"))
            for name in bundles:
                match = _TOKEN_RE.search(await self._get_text(SITE + name))
                if match:
                    return match.group(1)
        except (aiohttp.ClientError, TimeoutError) as err:
            raise StoerungsauskunftError(f"Website nicht erreichbar: {err}") from err
        raise StoerungsauskunftAuthError("basicAuth im Frontend-Bundle nicht gefunden")

    async def _get_json(self, path: str, params: dict[str, str]) -> list[dict[str, Any]]:
        for attempt in (1, 2):
            async with self._lock:
                if not self._token:
                    self._token = await self.discover_token()
                token = self._token
            headers = {
                "User-Agent": USER_AGENT,
                "Accept": "application/json, text/plain, */*",
                "Authorization": f"Basic {token}",
                "Origin": SITE.rstrip("/"),
                "Referer": SITE,
            }
            try:
                async with self._session.get(
                    API_BASE + path, params=params, headers=headers, timeout=_TIMEOUT
                ) as resp:
                    if resp.status in (401, 403):
                        if attempt == 1:
                            _LOGGER.debug("Token abgelehnt (%s), hole neuen", resp.status)
                            self._token = None
                            continue
                        raise StoerungsauskunftAuthError(f"API lehnt Token ab ({resp.status})")
                    resp.raise_for_status()
                    text = await resp.text()
            except (aiohttp.ClientError, TimeoutError) as err:
                raise StoerungsauskunftError(f"API-Abruf {path} fehlgeschlagen: {err}") from err
            if not text.strip():
                return []
            try:
                data = json.loads(text)
            except ValueError as err:
                raise StoerungsauskunftError(f"Ungültige Antwort von {path}") from err
            return data if isinstance(data, list) else []
        raise StoerungsauskunftAuthError("Token ungültig")

    async def outages(self, sectors: list[int]) -> list[dict[str, Any]]:
        """Offizielle Störungen der Netzbetreiber (alle Sektoren in einem Aufruf)."""
        return await self._get_json(
            "outages",
            {"SectorTypes": ",".join(map(str, sectors)), "countryCode": "DE"},
        )

    async def user_notifications(self, sector: int) -> list[dict[str, Any]]:
        """Bürgermeldungen für einen Sektor."""
        return await self._get_json(
            "usernotification",
            {"SectorType": str(sector), "IncludeDisabled": "false", "countryCode": "DE"},
        )
