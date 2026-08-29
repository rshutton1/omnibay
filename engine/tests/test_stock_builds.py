"""Parity with the reference MwoLab client.

Every value in `fixtures/stock_builds.json` was produced by running the original
`public/app.js` over the same game data. If a formula drifts, these fail.
"""
import pytest

from omnibay.build import build_from_stock_loadout
from omnibay.calculate import calculate_build

TOLERANCE = 0.005


@pytest.fixture(scope="module")
def results(data, stock_build_expectations):
    computed = {}
    for mech in data.mechs:
        name = mech["name"]
        if name not in stock_build_expectations:
            continue
        build = build_from_stock_loadout(data, mech)
        computed[name] = calculate_build(data, mech, build)
    return computed


def _flatten(result):
    return {
        "maxTons": result["tonnage"]["max"],
        "totalTons": result["tonnage"]["used"],
        "heat": result["heat"]["alpha_heat"],
        "alpha": result["firepower"]["alpha_damage"],
        "ammo": result["firepower"]["ammo_shots"],
        "armor": result["armor"]["points"],
        "totalSlotCapacity": result["slots"]["total"],
        "currentSlotUsage": result["slots"]["used"],
        "freeSlots": result["slots"]["free"],
        "totalHeatSinkCount": result["heat"]["heat_sinks"],
        "requiredStructureSlots": result["slots"]["structure_upgrade"],
        "requiredArmorSlots": result["slots"]["armor_upgrade"],
        "engineRating": (result["engine"] or {}).get("rating"),
    }


def test_every_mech_has_an_expectation(data, stock_build_expectations):
    assert len(stock_build_expectations) == len(data.mechs)


def test_summary_values_match_reference(results, stock_build_expectations):
    failures = []
    for name, expected in stock_build_expectations.items():
        actual = _flatten(results[name])
        for field, want in expected.items():
            if field == "componentSlots":
                continue
            got = actual[field]
            if want is None or got is None:
                if want != got:
                    failures.append((name, field, want, got))
            elif abs(float(got) - float(want)) > TOLERANCE:
                failures.append((name, field, want, got))
    assert not failures, "mismatches: {0}".format(failures[:20])


def test_component_slot_usage_matches_reference(results, stock_build_expectations):
    failures = []
    for name, expected in stock_build_expectations.items():
        components = results[name]["components"]
        for component, want in expected["componentSlots"].items():
            got = components[component]["slots"]
            if got != want:
                failures.append((name, component, want, got))
    assert not failures, "mismatches: {0}".format(failures[:20])


# AS7-D-DC(E) is a scripted escort unit carrying 95 tons of armor on a 100 ton
# chassis. It is not player-buildable, and the reference client reports it as
# overweight too, so it is data to reproduce rather than a bug to fix.
KNOWN_OVERWEIGHT = {"as7-d-dc-escort"}


def test_stock_builds_are_within_tonnage(results):
    overweight = {
        name for name, result in results.items() if result["tonnage"]["overweight"]
    }
    assert overweight == KNOWN_OVERWEIGHT


def test_stock_builds_fit_their_slots(results):
    over = [
        (name, component)
        for name, result in results.items()
        for component, usage in result["components"].items()
        if usage["slot_limit"] and usage["slots"] > usage["slot_limit"]
    ]
    assert not over, "components over slot limit: {0}".format(over[:10])
