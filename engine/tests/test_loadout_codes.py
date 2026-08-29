"""MWO loadout codes survive a round trip for every variant in the game data."""
import pytest

from omnibay import codec
from omnibay.build import (
    build_from_decoded_code,
    build_from_stock_loadout,
    build_to_mwo_code,
)
from omnibay.calculate import calculate_build

# Engine-bay heat sinks are exported inside the centre torso and migrated back
# out on import, which permutes that component's item order. The item set and
# every derived number are unchanged, and the reference client does the same.
REORDERING_VARIANTS = {"bnc-3s", "bnc-3sp", "zeu-6s", "zeu-6sr", "zeu-6t"}


@pytest.fixture(scope="module")
def round_trips(data):
    trips = []
    for mech in data.mechs:
        build = build_from_stock_loadout(data, mech)
        code = build_to_mwo_code(data, mech, build)
        reimported = build_from_decoded_code(data, mech, codec.decode(code))
        trips.append((mech, build, code, reimported))
    return trips


def test_every_stock_build_exports(round_trips):
    assert len(round_trips) > 1000
    for mech, _build, code, _reimported in round_trips:
        assert code.startswith("A"), mech["name"]
        assert len(code) >= codec.MIN_LENGTH, mech["name"]


def test_round_trip_preserves_every_derived_value(data, round_trips):
    failures = []
    for mech, build, _code, reimported in round_trips:
        before = calculate_build(data, mech, build)
        after = calculate_build(data, mech, reimported)
        for section in ("tonnage", "slots", "armor", "firepower", "heat"):
            if before[section] != after[section]:
                failures.append((mech["name"], section))
                break
    assert not failures, "round trip changed results for: {0}".format(failures[:10])


def test_round_trip_preserves_the_item_set(data, round_trips):
    failures = []
    for mech, build, _code, reimported in round_trips:
        def item_ids(state):
            ids = []
            for component in state["components"].values():
                ids.extend(entry["item_id"] for entry in component["items"])
            ids.extend(entry["item_id"] for entry in state["engine_heat_sinks"])
            return sorted(ids)

        if item_ids(build) != item_ids(reimported):
            failures.append(mech["name"])
    assert not failures, "round trip changed installed items for: {0}".format(failures[:10])


def test_codes_are_stable_except_for_known_reordering(data, round_trips):
    unstable = set()
    for mech, _build, code, reimported in round_trips:
        if build_to_mwo_code(data, mech, reimported) != code:
            unstable.add(mech["name"])
    assert unstable == REORDERING_VARIANTS


def test_vtr_9sc_keeps_its_double_heat_sinks(data):
    """The extracted data spells this variant's upgrade key `ItemId`."""
    mech = data.mech_by_name("vtr-9sc")
    build = build_from_stock_loadout(data, mech)
    assert build["upgrades"]["heatsinks"] == 3002
    assert calculate_build(data, mech, build)["heat"]["double"] is True
