"""Quirk aggregation and classification."""
import pytest

from omnibay.quirks import (
    QuirkCollector,
    quirk_add,
    quirk_family,
    quirk_filter_magnitude,
    quirk_is_beneficial,
    quirk_multiplier,
    quirk_value_text,
    quirk_values,
)


def test_collector_sums_by_normalized_name_and_keeps_sources():
    collector = QuirkCollector()
    collector.add({"name": "MISSILE_COOLDOWN_MULTIPLIER", "value": -0.15}, "set bonus")
    collector.add({"name": "missile_cooldown_multiplier", "value": -0.05}, "chassis")
    (quirk,) = collector.resolve()

    assert quirk["name"] == "missile_cooldown_multiplier"
    assert quirk["value"] == pytest.approx(-0.2)
    assert quirk["value_text"] == "-20%"
    assert quirk["sources"] == ["set bonus", "chassis"]
    assert len(quirk["contributions"]) == 2


def test_resolve_sorts_by_display_name():
    collector = QuirkCollector()
    collector.add({"name": "b_multiplier", "display_name": "Zulu", "value": 1})
    collector.add({"name": "a_multiplier", "display_name": "Alpha", "value": 1})
    assert [q["display_name"] for q in collector.resolve()] == ["Alpha", "Zulu"]


@pytest.mark.parametrize(
    "name,value,expected",
    [
        ("all_heat_multiplier", -0.05, "-5%"),
        ("all_velocity_multiplier", 0.15, "+15%"),
        ("armor_rt_additive", 9, "+9"),
        ("armor_rt_additive", -3, "-3"),
        ("x_multiplier", 0.025, "+2.5%"),
    ],
)
def test_value_text(name, value, expected):
    assert quirk_value_text(name, value) == expected


@pytest.mark.parametrize(
    "name,expected",
    [
        ("isautocannon20_cooldown_multiplier", "cooldown"),
        ("all_heat_multiplier", "heat"),
        ("overheatdamage_multiplier", "overheatdamage"),
        ("armor_rt_additive", "rt"),
        ("not-a-quirk", ""),
    ],
)
def test_family_extraction(name, expected):
    assert quirk_family(name) == expected


@pytest.mark.parametrize(
    "name,value,expected",
    [
        # Cost-like families are better when negative.
        ("all_heat_multiplier", -0.05, True),
        ("missile_cooldown_multiplier", -0.15, True),
        ("missile_spread_multiplier", 0.2, False),
        ("overheatdamage_multiplier", -0.2, True),
        # Everything else is better when positive.
        ("all_velocity_multiplier", 0.15, True),
        ("ballistic_range_multiplier", -0.1, False),
        ("armor_rt_additive", 9, True),
        # A zero quirk is neither.
        ("all_heat_multiplier", 0, None),
    ],
)
def test_benefit_classification(name, value, expected):
    assert quirk_is_beneficial(name, value) is expected


def test_multipliers_combine_additively_around_one():
    values = quirk_values(
        [{"name": "a_multiplier", "value": 0.1}, {"name": "b_multiplier", "value": 0.05}]
    )
    assert quirk_multiplier(values, ["a_multiplier", "b_multiplier"]) == pytest.approx(1.15)


def test_quirk_add_combines_all_and_specific_variants():
    values = quirk_values(
        [
            {"name": "armor_all_additive", "value": 4},
            {"name": "armor_rt_additive", "value": 6},
            {"name": "armor_lt_additive", "value": 99},
        ]
    )
    assert quirk_add(values, "armor", "rt") == 10


def test_filter_magnitude_scales_multipliers_to_percent():
    assert quirk_filter_magnitude("a_multiplier", -0.15) == pytest.approx(15)
    assert quirk_filter_magnitude("a_additive", -9) == pytest.approx(9)
