"""Weapon statistics with quirks applied.

The interesting cases are where a mech's quirks actually change a weapon: the
HBK-4G stacks a generic -15% cooldown with a weapon-specific -25% on its AC/20.
"""
import pytest

from omnibay import weapon_stats as W
from omnibay.build import build_from_stock_loadout, effective_quirks
from omnibay.weapon_stats import weapon_tooltip

AC20 = 1000
AC20_AMMO = 2000


@pytest.fixture
def hunchback(data):
    mech = data.mech_by_name("hbk-4g")
    build = build_from_stock_loadout(data, mech)
    return mech, build, effective_quirks(data, mech, build)


def test_quirks_stack_generic_and_weapon_specific_cooldown(data, hunchback):
    _mech, _build, quirks = hunchback
    tooltip = weapon_tooltip(data, data.item(AC20), quirks)

    # -15% COOLDOWN and -25% IS AC20 Cooldown combine to -40%.
    assert tooltip["cooldown"]["base"] == 3.75
    assert tooltip["cooldown"]["final"] == pytest.approx(2.25)
    assert tooltip["cooldown"]["changed"] is True


def test_unquirked_weapon_reports_no_change(data):
    """With no quirks at all, base and final must agree everywhere."""
    tooltip = weapon_tooltip(data, data.item(AC20), [])
    for field in ("damage", "heat", "cooldown"):
        assert tooltip[field]["changed"] is False, field
    assert tooltip["applied_effects"] == []


def test_dps_follows_the_shortened_cooldown(data, hunchback):
    _mech, _build, quirks = hunchback
    tooltip = weapon_tooltip(data, data.item(AC20), quirks)
    dps = tooltip["rates"]["dps"]
    assert dps["final"] > dps["base"]
    assert dps["final"] == pytest.approx(20 / 2.25, abs=0.01)


def test_damage_per_heat_is_unchanged_by_a_cooldown_quirk(data, hunchback):
    """Cooldown affects rate, not efficiency — DPH must stay put."""
    _mech, _build, quirks = hunchback
    tooltip = weapon_tooltip(data, data.item(AC20), quirks)
    assert tooltip["rates"]["dph"]["changed"] is False


def test_applied_effects_name_their_source(data, hunchback):
    _mech, _build, quirks = hunchback
    effects = weapon_tooltip(data, data.item(AC20), quirks)["applied_effects"]
    names = {entry["name"] for entry in effects}
    assert "IS AC20 Cooldown" in names
    assert all(entry["sources"] for entry in effects)
    cooldown_entries = [e for e in effects if "cooldown" in e["effects"]]
    assert len(cooldown_entries) >= 2, "generic and specific quirks both apply"


def test_range_quirk_scales_optimal_and_max(data, hunchback):
    _mech, _build, quirks = hunchback
    tooltip = weapon_tooltip(data, data.item(AC20), quirks)
    assert tooltip["optimal_range"]["final"] > tooltip["optimal_range"]["base"]
    assert tooltip["max_range"]["final"] > tooltip["max_range"]["base"]


def test_non_weapons_have_no_tooltip(data):
    assert weapon_tooltip(data, data.item(AC20_AMMO), []) is None


def test_every_weapon_produces_a_tooltip(data):
    """No weapon in the game data may blow up the hover card."""
    failures = []
    for item in data.items_of_type("weapon"):
        try:
            tooltip = weapon_tooltip(data, item, [])
            assert tooltip["name"]
            assert tooltip["cooldown"]["base"] >= 0
        except Exception as error:  # noqa: BLE001 - reporting all failures at once
            failures.append((item.get("name"), str(error)))
    assert not failures, failures[:5]


def test_ultra_autocannons_report_jam_statistics(data):
    ultras = [i for i in data.items_of_type("weapon") if W.is_ultra_autocannon(i)]
    assert ultras, "expected ultra autocannons in the game data"
    tooltip = weapon_tooltip(data, ultras[0], [])
    assert tooltip["jam_chance"]["base"] > 0
    assert tooltip["jam_duration"]["base"] > 0


def test_expected_cooldown_exceeds_raw_cooldown_for_jamming_weapons(data):
    """A weapon that can jam is slower in practice than its cooldown implies."""
    ultras = [i for i in data.items_of_type("weapon") if W.is_ultra_autocannon(i)]
    tooltip = weapon_tooltip(data, ultras[0], [])
    assert "expected_cooldown" in tooltip


def test_hitscan_weapons_omit_velocity(data):
    """A hitscan weapon has no travel time, so a velocity row would be noise."""
    hitscan = [i for i in data.items_of_type("weapon") if W.is_hitscan(i)]
    assert hitscan
    for item in hitscan[:5]:
        assert "velocity" not in weapon_tooltip(data, item, [])


def test_a_harmful_quirk_is_flagged(data):
    """A positive spread quirk widens the group, so it must read as harmful."""
    missiles = [
        i
        for i in data.items_of_type("weapon")
        if (i.get("stats") or {}).get("spread")
    ]
    assert missiles
    quirks = [{"name": "missile_spread_multiplier", "display_name": "MISSILE SPREAD", "value": 0.2}]
    effects = weapon_tooltip(data, missiles[0], quirks)["applied_effects"]
    assert any(entry["harmful"] for entry in effects)


def test_applied_effects_report_the_quirks_own_sign(data, hunchback):
    """A -15% cooldown quirk must not read as +15% just because the engine
    stores reduction magnitudes internally."""
    _mech, _build, quirks = hunchback
    effects = weapon_tooltip(data, data.item(AC20), quirks)["applied_effects"]
    cooldown = next(e for e in effects if e["name"] == "IS AC20 Cooldown")

    assert cooldown["value"] > 0, "internally a reduction magnitude"
    assert cooldown["quirk_value"] < 0, "displayed with the quirk's own sign"
    assert cooldown["quirk_value"] == pytest.approx(-0.25)
