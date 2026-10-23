from datetime import datetime, timedelta

import pytest

from custom_components.stoerungsauskunft.model import (
    TZ, AreaMatcher, Settings, evaluate, parse_codes,
)

NOW = datetime(2026, 10, 23, 21, 0, tzinfo=TZ)


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations():
    """Reine Logik-Tests brauchen keine HA-Instanz."""
    yield


S = Settings(window=30, min_reports=8, min_addresses=5, quiet=120)


def ts(minutes_ago):
    return (NOW - timedelta(minutes=minutes_ago)).strftime("%m/%d/%Y %H:%M:%S")


def test_parse_codes():
    assert parse_codes("66111, 66113;664  abc 66111") == ["66111", "66113", "664"]


def test_matcher_prefix():
    m = AreaMatcher(["66111", "664"])
    assert m("66111") and m("66424") and not m("66113")


def test_outages_active_planned_old():
    outs = [
        {"id": 1, "SectorType": 1, "postalCode": "66111", "dateStart": ts(10), "dateEnd": None,
         "operatorName": "Stadtwerke Saarbrücken Netz AG", "city": "Saarbrücken"},
        {"id": 2, "SectorType": 1, "postalCode": "66111", "dateStart": ts(-60), "dateEnd": ts(-120)},
        {"id": 3, "SectorType": 1, "postalCode": "66111", "dateStart": ts(300), "dateEnd": ts(120)},
        {"id": 4, "SectorType": 1, "postalCode": "10115", "dateStart": ts(10)},
        {"id": 5, "SectorType": 1, "postalCode": "66111", "dateStart": ts(10), "isFixed": True},
    ]
    r = evaluate(outs, {}, [1], AreaMatcher(["66111"]), S, NOW)[1]
    assert [o["id"] for o in r.outages] == [1]
    assert [o["id"] for o in r.planned] == [2]
    assert r.outages[0]["operator"] == "Stadtwerke Saarbrücken Netz"
    assert r.problem


def test_reports_cluster_and_privacy():
    reps = [{"id": i, "postalCode": "66133", "dateStart": ts(20 - i), "street": f"Weg {i % 6}",
             "houseNumber": "1", "comment": "geheim", "city": "Saarbrücken"} for i in range(9)]
    reps.append({"id": 99, "postalCode": "66133", "dateStart": ts(400), "street": "Alt"})
    r = evaluate([], {1: reps}, [1], AreaMatcher(["66133"]), S, NOW)[1]
    assert len(r.areas) == 1
    a = r.areas[0]
    assert a["reports"] == 9 and a["addresses"] == 6 and a["suspected"]
    assert r.report_count == 9 and r.problem
    flat = repr(r.areas)
    assert "Weg" not in flat and "geheim" not in flat and "houseNumber" not in flat


def test_reports_below_threshold_and_quiet():
    reps = [{"id": i, "postalCode": "66133", "dateStart": ts(10), "street": "A", "houseNumber": str(i)}
            for i in range(3)]
    old = [{"id": 50, "postalCode": "66111", "dateStart": ts(200), "street": "B"}]
    r = evaluate([], {1: reps + old}, [1], AreaMatcher(["661"]), S, NOW)[1]
    assert [a["postal_code"] for a in r.areas] == ["66133"]
    assert not r.suspected and not r.problem
