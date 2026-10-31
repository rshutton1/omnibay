"""Loadout-wide rates of fire: DPS, heat per second and heat efficiency.

The reference case is the Hellbringer HBR-AH missile boat shared as MechDB build
`5cd87023_HBR-AH`, which reads FIREPOWER 120.0, DPS (SUS/MAX) 11.0 / 35.6,
HEAT EFFICIENCY 31% and ALPHA HEAT 30.6. Its pods, weapons, ammo and heat sinks
are reproduced below; armor is left at stock, since none of these figures
depend on it.
"""
import pytest

from omnibay.build import build_from_stock_loadout
from omnibay.calculate import calculate_build

C_SRM_6 = 1228
C_SRM_AMMO = 2216
C_SRM_AMMO_HALF = 2236
CLAN_DOUBLE_HEAT_SINK = 3004
C_ER_MICRO_LASER = 1244


def metrics_of(data, reference, layout):
    """Calculate `reference` with each named component re-podded and re-filled."""
    mech = data.mech_by_name(reference)
    build = build_from_stock_loadout(data, mech)
    for component in build["components"].values():
        component["items"] = []
    for component, (pod_set, item_ids) in layout.items():
        if pod_set:
            pod = data.find_omnipod(mech.get("chassis"), pod_set, component)
            assert pod, (pod_set, component)
            build["components"][component]["omnipod"] = pod["id"]
        build["components"][component]["items"] = [
            {"item_id": item_id} for item_id in item_ids
        ]
    return calculate_build(data, mech, build)


@pytest.fixture(scope="module")
def srm_hellbringer(data):
    """The MechDB build: ten C-SRM 6 behind the missile cooldown and heat pods."""
    return metrics_of(
        data,
        "hbr-ah",
        {
            "right_arm": ("hbr-vi", [C_SRM_6] * 2),
            "right_torso": (
                "hbr-b",
                [C_SRM_6] * 2 + [C_SRM_AMMO] * 2 + [CLAN_DOUBLE_HEAT_SINK],
            ),
            "right_leg": ("hbr-ah", [C_SRM_AMMO, C_SRM_AMMO_HALF]),
            "head": ("hbr-prime", [C_SRM_AMMO]),
            # The other three sinks ride in the engine's own slots, which the
            # stock loadout already fills, so they are not listed here.
            "centre_torso": ("hbr-ah", [C_SRM_6] * 2),
            "left_torso": ("hbr-p", [C_SRM_6, C_SRM_AMMO]),
            "left_leg": ("hbr-ah", [C_SRM_AMMO] * 2),
            "left_arm": ("hbr-ah", [C_SRM_6] * 3),
        },
    )


def test_reference_build_matches_mechdb(srm_hellbringer):
    result = srm_hellbringer
    # Ten C-SRM 6 at 12 damage each, over seven and a half tons of ammo.
    assert result["firepower"]["alpha_damage"] == 120.0
    assert result["firepower"]["ammo_shots"] == 900
    # 3.4 heat each, less the right torso pod's 10% missile heat quirk.
    assert result["weapons"]["alpha_heat"] == 30.6
    # 3.75s cooldown, less the left torso pod's 10% missile cooldown quirk.
    assert result["weapons"]["dps"] == 35.56
    # Fourteen double heat sinks shedding 0.2/s against 9.07 heat per second.
    assert result["heat"]["dissipation"] == 2.8
    assert result["weapons"]["hps"] == 9.07
    assert result["weapons"]["heat_efficiency"] == 30.9
    assert result["weapons"]["sustained_dps"] == 10.98


def test_sustained_dps_is_dps_at_heat_efficiency(srm_hellbringer):
    weapons = srm_hellbringer["weapons"]
    # Both sides are rounded for display, so this agrees to within a rounding step.
    assert weapons["sustained_dps"] == pytest.approx(
        weapons["dps"] * weapons["heat_efficiency"] / 100, abs=0.02
    )


def test_alpha_heat_percent_is_the_share_of_capacity(srm_hellbringer):
    result = srm_hellbringer
    assert result["weapons"]["alpha_heat_percent"] == round(
        result["weapons"]["alpha_heat"] / result["heat"]["capacity"] * 100, 1
    )


def test_alpha_heat_counts_quirks_unlike_the_raw_item_total(srm_hellbringer):
    # `heat.alpha_heat` is raw item heat held to reference parity; the weapons
    # block is what a pilot actually generates, so the quirk has to show.
    assert srm_hellbringer["weapons"]["alpha_heat"] == 30.6
    assert srm_hellbringer["heat"]["alpha_heat"] == 34.0


def test_a_loadout_within_its_cooling_sustains_full_rate(data):
    """One micro laser generates far less heat than a Dire Wolf's sinks shed."""
    weapons = metrics_of(
        data, "dwf-prime", {"left_arm": (None, [C_ER_MICRO_LASER])}
    )["weapons"]

    assert weapons["hps"] > 0
    assert weapons["heat_efficiency"] == 100.0
    assert weapons["sustained_dps"] == weapons["dps"]


def test_a_mech_with_no_weapons_reports_zero(data):
    weapons = metrics_of(data, "hbr-ah", {})["weapons"]

    assert weapons["dps"] == 0.0
    assert weapons["sustained_dps"] == 0.0
    assert weapons["alpha_heat"] == 0.0
    assert weapons["alpha_heat_percent"] == 0.0
    # Nothing firing is trivially within the cooling budget.
    assert weapons["heat_efficiency"] == 100.0


def test_rotary_heat_is_already_per_second(data):
    """The Chip's two Rotary AC/5 state 3.25 heat a second each, not per shot."""
    mech = data.mech_by_name("chp-ap")
    weapons = calculate_build(data, mech, build_from_stock_loadout(data, mech))["weapons"]

    assert weapons["alpha_heat"] == 6.5
    # Their tenth-of-a-second cycle would otherwise inflate this tenfold.
    assert weapons["hps"] == 6.5


def test_a_volley_weapon_is_timed_by_its_whole_burst(data):
    """The stock Hellbringer: five C-LRM 10 and three C-Medium Pulse Lasers.

    An LRM 10 goes out as five volleys of two, 0.05s apart, so a trigger pull
    takes 4.2s rather than the 4.0s cooldown the item states.
    """
    mech = data.mech_by_name("hbr-ah")
    weapons = calculate_build(data, mech, build_from_stock_loadout(data, mech))["weapons"]

    assert weapons["dps"] == round(5 * 10 / 4.2 + 3 * 7 / 3.8, 2) == 17.43
