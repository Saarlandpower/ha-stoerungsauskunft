"""Auswertung der API-Daten – ohne Home-Assistant-Abhängigkeiten (testbar).

Datenschutz: Bürgermeldungen enthalten Straße, Hausnummer und Freitext. Diese
Felder werden hier nur intern zum Zählen eindeutiger Adressen verwendet und
NIE in die Ergebnisse übernommen. Ausgegeben werden nur PLZ, Ort, Netzbetreiber,
Anzahlen und Zeitpunkte.
"""
from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from .const import CLUSTER_GAP, SAARLAND_PLZ, TIMEZONE, TS_FORMAT

TZ = ZoneInfo(TIMEZONE)


@dataclass
class Settings:
    window: int
    min_reports: int
    min_addresses: int
    quiet: int


@dataclass
class SectorState:
    """Ergebnis für einen Sektor im konfigurierten Gebiet."""

    outages: list[dict[str, Any]] = field(default_factory=list)   # aktive offizielle
    planned: list[dict[str, Any]] = field(default_factory=list)   # angekündigt, noch nicht begonnen
    areas: list[dict[str, Any]] = field(default_factory=list)     # laufende Meldungs-Häufungen

    @property
    def report_count(self) -> int:
        return sum(a["reports"] for a in self.areas)

    @property
    def suspected(self) -> bool:
        return any(a["suspected"] for a in self.areas)

    @property
    def problem(self) -> bool:
        return bool(self.outages) or self.suspected


class AreaMatcher:
    """PLZ-Filter. Einträge mit weniger als 5 Stellen gelten als Präfix."""

    def __init__(self, codes: list[str]) -> None:
        self.exact = {c for c in codes if len(c) == 5}
        self.prefixes = tuple(c for c in codes if 0 < len(c) < 5)

    def __call__(self, plz: str) -> bool:
        return plz in self.exact or (bool(self.prefixes) and plz.startswith(self.prefixes))


def parse_codes(raw: str) -> list[str]:
    """'66111, 66113 6642' -> ['66111', '66113', '6642'] (nur Ziffern, 1–5 Stellen)."""
    out = []
    for tok in re.split(r"[\s,;]+", raw or ""):
        if tok.isdigit() and 1 <= len(tok) <= 5 and tok not in out:
            out.append(tok)
    return out


def parse_ts(value: Any) -> datetime | None:
    try:
        return datetime.strptime(value, TS_FORMAT).replace(tzinfo=TZ)
    except (TypeError, ValueError):
        return None


def short_operator(name: str | None) -> str | None:
    if not name:
        return None
    n = re.sub(r"\s*(GmbH\s*&\s*Co\.?\s*KG|GmbH|mbH|AG|AöR|KG|e\.\s?V\.)\b\.?", "", name)
    return re.sub(r"\s{2,}", " ", n).strip(" ,-") or None


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


def _sector_of(item: dict[str, Any]) -> int | None:
    val = item.get("SectorType", item.get("sectorType"))
    try:
        return int(val)
    except (TypeError, ValueError):
        return None


def _city(item: dict[str, Any], plz: str) -> str | None:
    return item.get("city") or (SAARLAND_PLZ.get(plz) or [None])[0]


def _addr_key(r: dict[str, Any]) -> str:
    if r.get("street"):
        return f"{r.get('street')}|{r.get('houseNumber')}"
    return str(r.get("coordinates") or r.get("id"))


def _outage_entry(o: dict[str, Any], plz: str, start, end) -> dict[str, Any]:
    district = o.get("district")
    city = _city(o, plz)
    return {
        "id": o.get("id"),
        "postal_code": plz,
        "city": city,
        "district": district if district and district != city else None,
        "operator": short_operator(o.get("operatorName")),
        "start": _iso(start),
        "end": _iso(end),
        "last_update": _iso(parse_ts(o.get("lastUpdate"))),
    }


def _clusters(reports: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    out: list[list[dict[str, Any]]] = []
    cur: list[dict[str, Any]] = []
    last = None
    for r in sorted(reports, key=lambda x: x["_ts"]):
        if last and r["_ts"] - last > timedelta(minutes=CLUSTER_GAP):
            out.append(cur)
            cur = []
        cur.append(r)
        last = r["_ts"]
    if cur:
        out.append(cur)
    return out


def _peak(cluster: list[dict[str, Any]], window: int) -> tuple[int, int]:
    """Max. Meldungen / Adressen innerhalb eines gleitenden Fensters."""
    best_n = best_a = 0
    j = 0
    for i, r in enumerate(cluster):
        while r["_ts"] - cluster[j]["_ts"] > timedelta(minutes=window):
            j += 1
        win = cluster[j : i + 1]
        n, a = len(win), len({_addr_key(x) for x in win})
        if (n, a) > (best_n, best_a):
            best_n, best_a = n, a
    return best_n, best_a


def evaluate(
    outages: list[dict[str, Any]],
    reports: dict[int, list[dict[str, Any]]],
    sectors: list[int],
    match: AreaMatcher,
    settings: Settings,
    now: datetime,
) -> dict[int, SectorState]:
    result = {s: SectorState() for s in sectors}

    # --- offizielle Störungen
    for o in outages or []:
        sector = _sector_of(o)
        plz = str(o.get("postalCode") or "").strip()
        if sector not in result or not match(plz) or o.get("isFixed"):
            continue
        start, end = parse_ts(o.get("dateStart")), parse_ts(o.get("dateEnd"))
        if start and start > now:
            result[sector].planned.append(_outage_entry(o, plz, start, end))
            continue
        if end is None and start and now - start > timedelta(days=3):
            continue                       # Altlast ohne Endzeit
        if end is not None and end <= now - timedelta(minutes=30):
            continue                       # vorbei
        result[sector].outages.append(_outage_entry(o, plz, start, end))

    # --- Bürgermeldungen
    for sector, items in reports.items():
        if sector not in result:
            continue
        groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for r in items or []:
            plz = str(r.get("postalCode") or "").strip()
            ts = parse_ts(r.get("dateStart"))
            if ts and match(plz) and not r.get("disabled"):
                groups[plz].append({**r, "_ts": ts})
        for plz, reps in groups.items():
            cl = _clusters(reps)[-1]
            first, last = cl[0]["_ts"], cl[-1]["_ts"]
            if now - last > timedelta(minutes=settings.quiet):
                continue                   # Häufung vorbei
            recent = [r for r in cl if r["_ts"] >= now - timedelta(minutes=settings.window)]
            peak_n, peak_a = _peak(cl, settings.window)
            result[sector].areas.append({
                "postal_code": plz,
                "city": _city(cl[-1], plz),
                "operator": short_operator(cl[-1].get("operatorName")),
                "reports": len(cl),
                "addresses": len({_addr_key(r) for r in cl}),
                "recent_reports": len(recent),
                "since": _iso(first),
                "last": _iso(last),
                "suspected": peak_n >= settings.min_reports and peak_a >= settings.min_addresses,
                "confirmed": any(r.get("operatorOutageInArea") for r in cl),
            })

    for st in result.values():
        st.outages.sort(key=lambda x: (x["postal_code"], x["start"] or ""))
        st.planned.sort(key=lambda x: x["start"] or "")
        st.areas.sort(key=lambda x: -x["reports"])
    return result
