"""Konstanten für die Störungsauskunft-Integration."""
from __future__ import annotations

from typing import Final

DOMAIN: Final = "stoerungsauskunft"

SITE: Final = "https://xn--strungsauskunft-9sb.de/"
SITE_HUMAN: Final = "störungsauskunft.de"
API_BASE: Final = "https://api-public.stoerungsauskunft.de/api/v1/public/"
USER_AGENT: Final = "HomeAssistant-Stoerungsauskunft/0.1 (+https://github.com/Saarlandpower/ha-stoerungsauskunft)"
TIMEZONE: Final = "Europe/Berlin"
TS_FORMAT: Final = "%m/%d/%Y %H:%M:%S"

# Sektoren laut Frontend von störungsauskunft.de
SECTORS: Final[dict[int, dict[str, str]]] = {
    1: {"key": "strom", "name": "Strom", "icon": "mdi:transmission-tower-off"},
    2: {"key": "gas", "name": "Gas", "icon": "mdi:fire-off"},
    3: {"key": "wasser", "name": "Wasser", "icon": "mdi:water-off"},
    7: {"key": "fernwaerme", "name": "Fernwärme", "icon": "mdi:radiator-off"},
}

CONF_AREA: Final = "area"
CONF_POSTAL_CODES: Final = "postal_codes"
CONF_SECTORS: Final = "sectors"
CONF_SCAN_INTERVAL: Final = "scan_interval"
CONF_WINDOW: Final = "window_minutes"
CONF_MIN_REPORTS: Final = "min_reports"
CONF_MIN_ADDRESSES: Final = "min_addresses"
CONF_QUIET: Final = "quiet_minutes"

AREA_SAARLAND: Final = "saarland"
AREA_CUSTOM: Final = "custom"

DEFAULT_SECTORS: Final = ["1"]
DEFAULT_SCAN_INTERVAL: Final = 5      # Minuten; kleiner ist nicht erlaubt (API schonen)
MIN_SCAN_INTERVAL: Final = 5
DEFAULT_WINDOW: Final = 30            # Minuten, in denen Meldungen gezählt werden
DEFAULT_MIN_REPORTS: Final = 8
DEFAULT_MIN_ADDRESSES: Final = 5
DEFAULT_QUIET: Final = 120            # Minuten ohne neue Meldung -> Häufung vorbei
CLUSTER_GAP: Final = 90               # Minuten Lücke trennt zwei Häufungen

EVENT_OUTAGE_NEW: Final = f"{DOMAIN}_outage_new"
EVENT_OUTAGE_RESOLVED: Final = f"{DOMAIN}_outage_resolved"
EVENT_SUSPECTED: Final = f"{DOMAIN}_suspected"

# Alle saarländischen PLZ (Stand Okt. 2026) -> Ort(e)
SAARLAND_PLZ: Final[dict[str, list[str]]] = {
    "66111": ["Saarbrücken"], "66113": ["Saarbrücken"], "66115": ["Saarbrücken"],
    "66117": ["Saarbrücken"], "66119": ["Saarbrücken"], "66121": ["Saarbrücken"],
    "66123": ["Saarbrücken"], "66125": ["Saarbrücken"], "66126": ["Saarbrücken"],
    "66127": ["Saarbrücken"], "66128": ["Saarbrücken"], "66129": ["Saarbrücken"],
    "66130": ["Saarbrücken"], "66131": ["Saarbrücken"], "66132": ["Saarbrücken"],
    "66133": ["Saarbrücken"], "66265": ["Heusweiler"], "66271": ["Kleinblittersdorf"],
    "66280": ["Sulzbach/Saar"], "66287": ["Quierschied"], "66292": ["Riegelsberg"],
    "66299": ["Friedrichsthal"], "66333": ["Völklingen"], "66346": ["Püttlingen"],
    "66352": ["Großrosseln"], "66359": ["Bous"], "66386": ["St. Ingbert"],
    "66399": ["Mandelbachtal"], "66424": ["Homburg"], "66440": ["Blieskastel"],
    "66450": ["Bexbach"], "66453": ["Gersheim"], "66459": ["Kirkel"],
    "66538": ["Neunkirchen"], "66539": ["Neunkirchen"], "66540": ["Neunkirchen"],
    "66557": ["Illingen"], "66564": ["Ottweiler"], "66571": ["Eppelborn"],
    "66578": ["Schiffweiler"], "66583": ["Spiesen-Elversberg"], "66589": ["Merchweiler"],
    "66606": ["Sankt Wendel"], "66620": ["Nonnweiler"], "66625": ["Nohfelden"],
    "66629": ["Freisen"], "66636": ["Tholey"], "66640": ["Namborn"],
    "66646": ["Marpingen"], "66649": ["Oberthal"], "66663": ["Merzig"],
    "66679": ["Losheim am See"], "66687": ["Wadern"], "66693": ["Mettlach"],
    "66701": ["Beckingen"], "66706": ["Perl"], "66709": ["Weiskirchen"],
    "66740": ["Saarlouis"], "66763": ["Dillingen/Saar"], "66773": ["Schwalbach"],
    "66780": ["Rehlingen-Siersburg"], "66787": ["Wadgassen"], "66793": ["Saarwellingen"],
    "66798": ["Wallerfangen"], "66802": ["Überherrn"], "66806": ["Ensdorf/Saar"],
    "66809": ["Nalbach"], "66822": ["Eppelborn", "Lebach"], "66839": ["Schmelz"],
}
