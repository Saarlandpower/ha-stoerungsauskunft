"""Config-Flow, Setup, Entitäten und Ereignisse mit gemockter API."""
from datetime import datetime, timedelta

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_capture_events

from custom_components.stoerungsauskunft.const import (
    API_BASE, DOMAIN, EVENT_OUTAGE_NEW, EVENT_OUTAGE_RESOLVED, SITE,
)
from custom_components.stoerungsauskunft.model import TZ


def _ts(minutes_ago: int) -> str:
    return (datetime.now(TZ) - timedelta(minutes=minutes_ago)).strftime("%m/%d/%Y %H:%M:%S")


OUTAGE = {"id": 7, "SectorType": 1, "postalCode": "66111", "city": "Saarbrücken",
          "dateStart": _ts(15), "dateEnd": None, "operatorName": "Energis-Netzgesellschaft mbH"}
REPORTS = [{"id": i, "sectorType": 1, "postalCode": "66133", "city": "Saarbrücken",
            "dateStart": _ts(10 - i), "street": f"Gasse {i}", "houseNumber": "2",
            "comment": "privat", "disabled": False} for i in range(9)]


def _mock_site(aioclient_mock, token="dGVzdDp0ZXN0"):
    aioclient_mock.get(SITE, text='<script src="main-ABC123.js"></script>')
    aioclient_mock.get(SITE + "main-ABC123.js", text=f'x={{basicAuth:"{token}"}}')


def _mock_api(aioclient_mock, outages, reports):
    aioclient_mock.get(API_BASE + "outages", json=outages)
    aioclient_mock.get(API_BASE + "usernotification", json=reports)


async def test_config_flow_saarland(hass: HomeAssistant, aioclient_mock) -> None:
    _mock_site(aioclient_mock)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    _mock_api(aioclient_mock, [], [])
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"name": "", "area": "saarland", "postal_codes": "", "sectors": ["1", "3"]})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Saarland"
    assert result["data"]["sectors"] == ["1", "3"]


async def test_config_flow_custom_needs_codes(hass: HomeAssistant, aioclient_mock) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"name": "", "area": "custom", "postal_codes": "abc", "sectors": ["1"]})
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"postal_codes": "no_postal_codes"}


async def test_setup_entities_and_events(hass: HomeAssistant, aioclient_mock, freezer) -> None:
    _mock_site(aioclient_mock)
    _mock_api(aioclient_mock, [OUTAGE], REPORTS)
    entry = MockConfigEntry(domain=DOMAIN, title="Saarland",
                            data={"area": "saarland", "postal_codes": "", "sectors": ["1"]})
    entry.add_to_hass(hass)
    new_events = async_capture_events(hass, EVENT_OUTAGE_NEW)
    resolved = async_capture_events(hass, EVENT_OUTAGE_RESOLVED)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    states = {s.entity_id: s for s in hass.states.async_all()}
    print(sorted(states))
    outages = next(s for e, s in states.items() if e.startswith("sensor.") and ("offizielle" in e or "official" in e))
    assert outages.state == "1"
    assert outages.attributes["outages"][0]["operator"] == "Energis-Netzgesellschaft"
    reports = next(s for e, s in states.items() if e.startswith("sensor.") and ("meldungen" in e or "reports" in e))
    assert reports.state == "9"
    assert "Gasse" not in str(reports.attributes) and "privat" not in str(reports.attributes)
    problem = next(s for e, s in states.items() if e.startswith("binary_sensor."))
    assert problem.state == "on"
    assert problem.attributes["suspected_postal_codes"] == ["66133"]
    assert not new_events  # erster Abruf merkt nur den Stand

    # Störung verschwindet -> Ereignis "behoben"
    aioclient_mock.clear_requests()
    _mock_site(aioclient_mock)
    _mock_api(aioclient_mock, [], [])
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    assert len(resolved) == 1 and resolved[0].data["postal_code"] == "66111"
    assert hass.states.get(problem.entity_id).state == "off"

    # Token läuft ab -> 401, neuer Token wird geholt
    aioclient_mock.clear_requests()
    _mock_site(aioclient_mock, token="bmV1Om5ldQ==")
    aioclient_mock.get(API_BASE + "outages", status=401)
    await entry.runtime_data.async_refresh()
    assert entry.runtime_data.last_update_success is False  # alle Mocks liefern 401

    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_options_flow(hass: HomeAssistant, aioclient_mock) -> None:
    _mock_site(aioclient_mock)
    _mock_api(aioclient_mock, [], [])
    entry = MockConfigEntry(domain=DOMAIN, title="Saarland",
                            data={"area": "saarland", "postal_codes": "", "sectors": ["1"]})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.options.async_configure(result["flow_id"], {
        "area": "custom", "postal_codes": "66625 66111", "sectors": ["1", "3"],
        "scan_interval": 10, "window_minutes": 30, "min_reports": 5,
        "min_addresses": 3, "quiet_minutes": 90})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    coord = entry.runtime_data
    assert coord.sectors == [1, 3]
    assert coord.match("66625") and not coord.match("66424")
    assert coord.update_interval.total_seconds() == 600
    assert len([s for s in hass.states.async_all() if "storungsauskunft" in s.entity_id]) == 6
