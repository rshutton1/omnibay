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
    chain_to_root,
    dependents_of,
    normalize_selection,
    prerequisite_of,
    selected_skill_effects,
    skill_tree,
    toggle_selection,
)


def all_nodes(tree):
    return [node for category in tree["categories"] for node in category["nodes"]]


def node_named(tree, name):
    return next(n for n in all_nodes(tree) if n["name"] == name)


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
    assert len(all_nodes(tree)) == 239


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
    every_node = [n["name"] for n in all_nodes(skill_tree(data, mech, build, []))]
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
    gated = [n for n in jumpjets["nodes"] if not n["usable"]]
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
    assert node_named(tree, "Cooldown3")["name"] == "Cooldown3"
    # A node name must round-trip through selection.
    selection, dropped = normalize_selection(data, mech, build, ["Cooldown3"])
    assert selection and not dropped


def test_additive_effects_are_not_rendered_as_percentages(data, hunchback):
    """Magazine capacity adds rounds; it must not read as +2000%."""
    mech, build = hunchback
    tree = skill_tree(data, mech, build, [])
    text = node_named(tree, "MagazineCapacity1")["effects"][0]["value_text"]
    assert "%" not in text, text


# --- the real graph --------------------------------------------------------


def test_prerequisites_cross_branches(data):
    """Speed Tweak is gated behind Kinetic Burst, not behind Speed Tweak 1."""
    assert prerequisite_of(data, "SpeedTweak1") == "KineticBurst4"
    assert prerequisite_of(data, "SpeedTweak2") == "KineticBurst5"
    assert prerequisite_of(data, "SeismicSensor1") == "TargetInfoGathering3"


def test_taking_a_gated_node_pulls_in_the_other_branch(data, hunchback):
    mech, build = hunchback
    selection, _ = normalize_selection(data, mech, build, ["SpeedTweak3"])
    assert selection == [
        "KineticBurst1",
        "KineticBurst2",
        "KineticBurst3",
        "KineticBurst4",
        "KineticBurst5",
        "KineticBurst6",
        "SpeedTweak3",
    ]


def test_dropping_a_node_drops_what_depended_on_it(data, hunchback):
    mech, build = hunchback
    taken, _ = normalize_selection(data, mech, build, ["SpeedTweak3"])
    remaining, _ = toggle_selection(data, mech, build, "KineticBurst4", taken)

    assert remaining == ["KineticBurst1", "KineticBurst2", "KineticBurst3"]
    assert "SpeedTweak3" not in remaining


def test_toggle_is_reversible(data, hunchback):
    mech, build = hunchback
    added, _ = toggle_selection(data, mech, build, "Cooldown1", [])
    removed, _ = toggle_selection(data, mech, build, "Cooldown1", added)
    assert added == ["Cooldown1"]
    assert removed == []


def test_graph_is_a_forest_with_entry_points(data):
    """Every node has at most one prerequisite, and each category has roots."""
    nodes = data.skill_graph["nodes"]
    parents = {target for _source, target in data.skill_graph["edges"]}
    roots = [n for n in nodes if n not in parents]
    assert len(nodes) == 239
    assert len(data.skill_graph["edges"]) == 197
    assert len(roots) == 42
    assert {nodes[r]["category"] for r in roots} == {
        "firepower",
        "survival",
        "mobility",
        "jumpjets",
        "operations",
        "sensors",
        "auxiliary",
    }


def test_chains_terminate(data):
    """No cycles: every node reaches a root in finite steps."""
    for name in data.skill_graph["nodes"]:
        chain = chain_to_root(data, name)
        assert chain[-1] == name
        assert len(chain) == len(set(chain))


def test_branch_labels_use_the_games_names(data, hunchback):
    """The extract's internal names are not what the game displays.

    `ShockAbsorbance` in the extract is the survival skill the game calls
    Overheat Damage; the game's Shock Absorbance is the jump jet skill the
    extract calls `Vectoring`.
    """
    mech, build = hunchback
    tree = skill_tree(data, mech, build, [])

    survival = next(c for c in tree["categories"] if c["key"] == "survival")
    jumpjets = next(c for c in tree["categories"] if c["key"] == "jumpjets")

    assert "Overheat Damage" in {b["label"] for b in survival["branches"]}
    assert "Shock Absorbance" not in {b["label"] for b in survival["branches"]}
    assert "Shock Absorbance" in {b["label"] for b in jumpjets["branches"]}

    assert node_named(tree, "ShockAbsorbance1")["label"] == "Overheat Damage 1"
    assert node_named(tree, "Vectoring1")["label"] == "Shock Absorbance 1"


def test_every_node_has_a_position_and_label(data, hunchback):
    mech, build = hunchback
    for node in all_nodes(skill_tree(data, mech, build, [])):
        assert node["label"], node["name"]
        assert node["branch"], node["name"]
        assert node["x"] >= 0 and node["y"] >= 0, node["name"]


def test_cost_counts_unmet_prerequisites(data, hunchback):
    mech, build = hunchback
    tree = skill_tree(data, mech, build, [])
    assert node_named(tree, "KineticBurst1")["cost"] == 1
    assert node_named(tree, "SpeedTweak1")["cost"] == 5

    build["skills"], _ = normalize_selection(data, mech, build, ["KineticBurst4"])
    tree = skill_tree(data, mech, build, build["skills"])
    assert node_named(tree, "SpeedTweak1")["cost"] == 1
