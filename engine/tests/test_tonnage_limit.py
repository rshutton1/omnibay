"""Overweight detection.

Exceeding the chassis tonnage limit by any amount makes a build unusable in
game, so the engine flags it exactly rather than tolerantly. The reference
client allowed a 0.1 t overage before complaining; this does not.
"""
import pytest

from omnibay.build import build_from_stock_loadout
from omnibay.calculate import calculate_build
from omnibay.constants import TONNAGE_EPSILON

STANDARD_HEAT_SINK = 3000


@pytest.fixture
def hunchback(data):
    mech = data.mech_by_name("hbk-4g")
    return mech, build_from_stock_loadout(data, mech)


def test_stock_build_sits_exactly_on_the_limit(data, hunchback):
    mech, build = hunchback
    result = calculate_build(data, mech, build)
    assert result["tonnage"]["used"] == result["tonnage"]["max"]
    assert result["tonnage"]["overweight"] is False
    assert result["tonnage"]["over_by"] == 0
    assert result["valid"] is True


def test_a_single_armor_point_over_is_invalid(data, hunchback):
    """The smallest possible overage — one armor point — must still register."""
    mech, build = hunchback
    build["components"]["left_arm"]["armor"] += 1
    result = calculate_build(data, mech, build)

    assert result["tonnage"]["overweight"] is True
    assert result["valid"] is False
    assert 0 < result["tonnage"]["over_by"] < 0.05
    assert any("Overweight" in warning for warning in result["warnings"])


def test_overage_below_the_old_tolerance_is_caught(data, hunchback):
    """Regression: a 0.1 t tolerance used to swallow overages this size."""
    mech, build = hunchback
    build["components"]["left_arm"]["armor"] += 2
    result = calculate_build(data, mech, build)

    assert 0 < result["tonnage"]["over_by"] < 0.1
    assert result["tonnage"]["overweight"] is True


def test_warning_shows_extra_precision_for_a_tiny_overage(data, hunchback):
    """A 0.03 t overage must not render as a tidy-looking '50.00 / 50.00'."""
    mech, build = hunchback
    build["components"]["left_arm"]["armor"] += 1
    (warning,) = [w for w in calculate_build(data, mech, build)["warnings"] if "Overweight" in w]
    assert "50.00 / 50.00" not in warning


def test_large_overage_is_reported_in_whole_tons(data, hunchback):
    mech, build = hunchback
    build["components"]["left_arm"]["items"].append(
        {"item_id": STANDARD_HEAT_SINK, "weapon_group": None}
    )
    result = calculate_build(data, mech, build)
    assert result["tonnage"]["over_by"] == pytest.approx(1.0)
    assert "Overweight by 1.00t (51.00 / 50.00)" in result["warnings"]


def test_removing_the_excess_restores_validity(data, hunchback):
    mech, build = hunchback
    build["components"]["left_arm"]["armor"] += 1
    assert calculate_build(data, mech, build)["valid"] is False

    build["components"]["left_arm"]["armor"] -= 1
    assert calculate_build(data, mech, build)["valid"] is True


def test_epsilon_only_absorbs_float_noise(data, hunchback):
    """The tolerance must be far smaller than one armor point of tonnage."""
    mech, build = hunchback
    result = calculate_build(data, mech, build)
    # Lightest armor point in the game data is ~1/38.4 t.
    assert TONNAGE_EPSILON < (1 / 38.4) / 1000
    assert result["tonnage"]["max"] > 0
