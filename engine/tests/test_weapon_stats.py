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


TARGETING_COMPUTER_MK_I = 9013


def test_targeting_computer_adds_critical_chance_and_velocity(data):
    """Equipment modifies weapons too, not just quirks.

    A Targeting Computer Mk I gives projectile weapons +1.14% critical chance
    and +10% velocity — the reference client shows exactly these figures.
    """
    computer = data.item(TARGETING_COMPUTER_MK_I)
    tooltip = weapon_tooltip(data, data.item(AC20), [], [computer])

    (source,) = tooltip["equipment_effects"]
    assert source["name"] == "TARGETING COMP. MK I"
    labels = {effect["label"]: effect["value_text"] for effect in source["effects"]}
    assert labels["PROJECTILE CRITICAL CHANCE"] == "+1.14%"
    assert labels["PROJECTILE VELOCITY"] == "+10%"


def test_targeting_computer_raises_the_reported_velocity(data):
    computer = data.item(TARGETING_COMPUTER_MK_I)
    without = weapon_tooltip(data, data.item(AC20), [], [])
    with_computer = weapon_tooltip(data, data.item(AC20), [], [computer])

    assert with_computer["velocity"]["final"] == pytest.approx(
        without["velocity"]["final"] * 1.1, rel=1e-3
    )


def test_equipment_and_quirk_velocity_bonuses_add(data, hunchback):
    """The HBK-4G's +25%/+20% velocity quirks stack with the computer's +10%."""
    _mech, _build, quirks = hunchback
    computer = data.item(TARGETING_COMPUTER_MK_I)
    tooltip = weapon_tooltip(data, data.item(AC20), quirks, [computer])
    base = tooltip["velocity"]["base"]
    assert tooltip["velocity"]["final"] == pytest.approx(base * (1 + 0.25 + 0.20 + 0.10), rel=1e-3)


def test_critical_chance_includes_the_equipment_bonus(data):
    computer = data.item(TARGETING_COMPUTER_MK_I)
    chances = weapon_tooltip(data, data.item(AC20), [], [computer])["critical_chance"]
    assert chances[0] == pytest.approx(0.0114)


def test_no_equipment_means_no_equipment_section(data):
    assert weapon_tooltip(data, data.item(AC20), [], [])["equipment_effects"] == []


# --- equipment cards -------------------------------------------------------

STD_HEAT_SINK = 3000
CLAN_ACTIVE_PROBE = 9002


def test_equipment_gets_a_card_of_its_own(data):
    """Hovering a non-weapon must describe it, not fall back to nothing."""
    from omnibay.weapon_stats import equipment_tooltip

    tooltip = equipment_tooltip(data, data.item(TARGETING_COMPUTER_MK_I), [])
    assert tooltip["kind"] == "equipment"
    assert tooltip["name"] == "TARGETING COMP. MK I"
    assert tooltip["description"]
    labels = {row["label"] for row in tooltip["rows"]}
    assert {"Tons", "Slots", "Health", "Max equipped"} <= labels


def test_a_targeting_computer_states_what_it_grants(data):
    """Its own card must show its effect without needing a weapon selected."""
    from omnibay.weapon_stats import equipment_tooltip

    grants = equipment_tooltip(data, data.item(TARGETING_COMPUTER_MK_I), [])["grants"]
    labels = {row["label"]: row["value"] for row in grants}
    assert labels["PROJECTILE VELOCITY"] == "+10%"
    assert labels["PROJECTILE CRITICAL CHANCE"].startswith("+1.14%")


def test_plain_equipment_grants_nothing(data):
    from omnibay.weapon_stats import equipment_tooltip

    assert equipment_tooltip(data, data.item(STD_HEAT_SINK), [])["grants"] == []


def test_heat_sink_card_reports_dissipation(data):
    from omnibay.weapon_stats import equipment_tooltip

    labels = {
        row["label"] for row in equipment_tooltip(data, data.item(STD_HEAT_SINK), [])["rows"]
    }
    assert "Dissipation" in labels
    assert "Heat capacity" in labels


def test_ammo_card_reports_shots(data):
    from omnibay.weapon_stats import equipment_tooltip

    rows = {r["label"]: r["value"] for r in equipment_tooltip(data, data.item(AC20_AMMO), [])["rows"]}
    assert rows["Shots"] == "10"


def test_weapons_do_not_produce_equipment_cards(data):
    from omnibay.weapon_stats import equipment_tooltip

    assert equipment_tooltip(data, data.item(AC20), []) is None


def test_every_installable_item_yields_some_card(data):
    """Whatever the pointer lands on, one of the two builders must handle it."""
    from omnibay.weapon_stats import equipment_tooltip

    missing = []
    for item in data.items.values():
        card = weapon_tooltip(data, item, []) or equipment_tooltip(data, item, [])
        if card is None or not card.get("name"):
            missing.append(item.get("name"))
    assert not missing, missing[:5]
