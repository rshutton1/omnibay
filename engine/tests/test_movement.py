"""Top speed, the first number a player looks at on a build.

Values are cross-checked against MechDB, which shows the Hellbringer HBR-AH at
81.0 / 54.0 kph and the Firemoth FMT-AL at 162.0 / 108.0.
"""
from omnibay.build import build_from_stock_loadout
from omnibay.calculate import calculate_build


def movement_of(data, reference, skills=None):
    mech = data.mech_by_name(reference)
    build = build_from_stock_loadout(data, mech)
    if skills is not None:
        build["skills"] = list(skills)
    return calculate_build(data, mech, build)["movement"]


def test_speed_is_engine_rating_over_tonnage(data):
    # 325 rating / 65 tons * 16.2 MaxMovementSpeed
    assert movement_of(data, "hbr-ah")["speed"] == 81.0
    # 200 / 20 * 16.2
    assert movement_of(data, "fmt-al")["speed"] == 162.0


def test_reverse_speed_uses_the_chassis_multiplier(data):
    assert round(movement_of(data, "hbr-ah")["reverse_speed"]) == 54
    assert round(movement_of(data, "fmt-al")["reverse_speed"]) == 108


def test_speed_tweak_raises_both_directions(data):
    base = movement_of(data, "hbr-ah")
    # one rank of Speed Tweak is +1.5% top speed, applying forward and reverse
    tweaked = movement_of(data, "hbr-ah", ["SpeedTweak1"])

    assert tweaked["speed"] == round(base["speed"] * 1.015, 2)
    assert tweaked["reverse_speed"] > base["reverse_speed"]
    # the unmodified figure is kept so the UI can show what the bonus is doing
    assert tweaked["base_speed"] == base["speed"]


def test_a_mech_with_no_engine_has_no_speed(data):
    mech = data.mech_by_name("hbk-4g")
    build = build_from_stock_loadout(data, mech)
    for component in build["components"].values():
        component["items"] = []

    movement = calculate_build(data, mech, build)["movement"]
    assert movement["speed"] == 0.0
    assert movement["reverse_speed"] == 0.0
