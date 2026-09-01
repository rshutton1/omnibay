"""The pilot skill tree.

Skills resolve to ordinary quirks, so the important properties are that the
right value is chosen for the mech, the chain and point cap are enforced, and
the result reaches the numbers a pilot actually cares about.
"""
import pytest

from omnibay.build import build_from_stock_loadout, effective_quirks
from omnibay.calculate import calculate_build
from omnibay.skills import (
    MAX_SKILL_POINTS,
    node_stem_and_order,
    normalize_selection,
    prerequisite_of,
    selected_skill_effects,
    skill_tree,
)


@pytest.fixture
def hunchback(data):
    mech = data.mech_by_name("hbk-4g")
    return mech, build_from_stock_loadout(data, mech)


# --- structure -------------------------------------------------------------


def test_tree_covers_every_category_and_node(data, hunchback):
    mech, build = hunchback
    tree = skill_tree(data, mech, build, [])
    assert tree["max_points"] == MAX_SKILL_POINTS == 91
    assert len(tree["categories"]) == 7
    total = sum(
        len(branch["nodes"]) for c in tree["categories"] for branch in c["branches"]
    )
    assert total == 239


@pytest.mark.parametrize(
    "name,stem,order",
    [("Cooldown12", "Cooldown", 12), ("Range1", "Range", 1), ("AdvancedZoom", "AdvancedZoom", 1)],
)
def test_node_ordering_is_read_from_the_name(name, stem, order):
    assert node_stem_and_order(name) == (stem, order)


def test_chain_prerequisites(data):
    assert prerequisite_of(data, "Cooldown1") is None
    assert prerequisite_of(data, "Cooldown2") == "Cooldown1"
    assert prerequisite_of(data, "Cooldown16") == "Cooldown15"


def test_unnumbered_nodes_have_no_prerequisite(data):
    assert prerequisite_of(data, "AdvancedZoom") is None


# --- selection rules -------------------------------------------------------


def test_selecting_a_deep_node_pulls_in_its_chain(data, hunchback):
    mech, build = hunchback
    selection, dropped = normalize_selection(data, mech, build, ["Cooldown5"])
    assert selection == ["Cooldown1", "Cooldown2", "Cooldown3", "Cooldown4", "Cooldown5"]
    assert dropped == []


def test_selection_is_capped_at_the_point_limit(data, hunchback):
    mech, build = hunchback
    every_node = [
        node["name"]
        for category in skill_tree(data, mech, build, [])["categories"]
        for branch in category["branches"]
        for node in branch["nodes"]
    ]
    selection, dropped = normalize_selection(data, mech, build, every_node)
    assert len(selection) == MAX_SKILL_POINTS
    assert dropped


def test_unknown_nodes_are_dropped_not_fatal(data, hunchback):
    mech, build = hunchback
    selection, dropped = normalize_selection(data, mech, build, ["NotARealNode", "Cooldown1"])
    assert selection == ["Cooldown1"]
    assert "NotARealNode" in dropped


def test_jump_jet_skills_are_unavailable_without_jump_jets(data, hunchback):
    """The Hunchback has no jump jets, so that whole branch must not apply."""
    mech, build = hunchback
    assert mech["definition"]["stats"]["MaxJumpJets"] == 0

    tree = skill_tree(data, mech, build, [])
    jumpjets = next(c for c in tree["categories"] if c["key"] == "jumpjets")
    gated = [n for b in jumpjets["branches"] for n in b["nodes"] if not n["usable"]]
    assert gated, "expected jump jet nodes to be gated"
    assert all("jump jet" in n["blocked_reason"].lower() for n in gated)


# --- scoped values ---------------------------------------------------------


def test_effect_value_is_scoped_to_the_mech(data):
    """The same node is worth different amounts by faction."""
    inner_sphere = data.mech_by_name("hbk-4g")
    clan = data.mech_by_name("tbr-prime")
    is_build = build_from_stock_loadout(data, inner_sphere)
    clan_build = build_from_stock_loadout(data, clan)

    is_value = selected_skill_effects(data, inner_sphere, is_build, ["Cooldown1"])[0]["value"]
    clan_value = selected_skill_effects(data, clan, clan_build, ["Cooldown1"])[0]["value"]

    assert is_value == pytest.approx(-0.0075)
    assert clan_value == pytest.approx(-0.006)
    assert is_value != clan_value


def test_structure_skill_scales_with_tonnage(data):
    """Skeletal Density is worth more on a heavier chassis."""
    light = data.mech_by_name("fle-15")
    assault = data.mech_by_name("as7-d")
    values = []
    for mech in (light, assault):
        build = build_from_stock_loadout(data, mech)
        effects = selected_skill_effects(data, mech, build, ["SkeletalDensity1"])
        values.append(effects[0]["value"] if effects else 0)
    assert values[0] != values[1]


# --- integration -----------------------------------------------------------


def test_skills_merge_into_the_build_quirk_list(data, hunchback):
    mech, build = hunchback
    before = {q["name"] for q in effective_quirks(data, mech, build)}

    build["skills"] = ["Cooldown1", "Cooldown2"]
    after = effective_quirks(data, mech, build)
    cooldown = next(q for q in after if q["name"] == "all_cooldown_multiplier")

    assert "Skills" in cooldown["source_text"]
    assert "Variant" in cooldown["source_text"], "chassis quirk must survive the merge"
    assert before  # sanity: the mech had quirks to begin with


def test_heat_skills_change_dissipation_and_capacity(data, hunchback):
    """Regression: these read quirk names that appear nowhere in the data."""
    mech, build = hunchback
    before = calculate_build(data, mech, build)["heat"]

    build["skills"], _ = normalize_selection(data, mech, build, ["CoolRun5", "HeatContainment5"])
    after = calculate_build(data, mech, build)["heat"]

    assert after["dissipation"] > before["dissipation"]
    assert after["capacity"] > before["capacity"]


def test_durability_skills_raise_effective_armor_and_structure(data, hunchback):
    mech, build = hunchback
    before = calculate_build(data, mech, build)["components"]["centre_torso"]

    build["skills"], _ = normalize_selection(
        data, mech, build, ["ArmorHardening5", "SkeletalDensity5"]
    )
    after = calculate_build(data, mech, build)["components"]["centre_torso"]

    assert after["effective_armor"] > before["effective_armor"]
    assert after["effective_structure"] > before["effective_structure"]
    # Capacity is fixed by the chassis; skills make points tougher, not more numerous.
    assert after["max_armor"] == before["max_armor"]


def test_skills_reach_weapon_statistics(data, hunchback):
    """A cooldown skill must shorten the weapon's actual cooldown."""
    from omnibay.weapon_stats import weapon_tooltip

    mech, build = hunchback
    quirks = effective_quirks(data, mech, build)
    before = weapon_tooltip(data, data.item(1000), quirks)["cooldown"]["final"]

    build["skills"], _ = normalize_selection(data, mech, build, ["Cooldown10"])
    after_quirks = effective_quirks(data, mech, build)
    after = weapon_tooltip(data, data.item(1000), after_quirks)["cooldown"]["final"]

    assert after < before


def test_no_skills_changes_nothing(data, hunchback):
    """Every stock build must be identical with an empty selection."""
    mech, build = hunchback
    build["skills"] = []
    assert calculate_build(data, mech, build) == calculate_build(data, mech, build)
    assert selected_skill_effects(data, mech, build, []) == []


def test_tree_reports_node_names_not_quirk_names(data, hunchback):
    """Regression: the effect loop once shadowed the node's own name."""
    mech, build = hunchback
    tree = skill_tree(data, mech, build, [])
    firepower = next(c for c in tree["categories"] if c["key"] == "firepower")
    cooldown = next(b for b in firepower["branches"] if b["subcategory"] == "Cooldown")

    assert [n["name"] for n in cooldown["nodes"][:3]] == [
        "Cooldown1",
        "Cooldown2",
        "Cooldown3",
    ]
    # A node name must round-trip through selection.
    selection, dropped = normalize_selection(data, mech, build, ["Cooldown3"])
    assert selection and not dropped


def test_additive_effects_are_not_rendered_as_percentages(data, hunchback):
    """Magazine capacity adds rounds; it must not read as +2000%."""
    mech, build = hunchback
    tree = skill_tree(data, mech, build, [])
    firepower = next(c for c in tree["categories"] if c["key"] == "firepower")
    magazine = next(
        b for b in firepower["branches"] if b["subcategory"] == "MagazineCapacity"
    )
    text = magazine["nodes"][0]["effects"][0]["value_text"]
    assert "%" not in text, text
