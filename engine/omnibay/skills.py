"""The pilot skill tree.

Skill nodes produce ordinary quirks — `all_cooldown_multiplier`,
`mechtopspeed_multiplier` and the like — so once a selection is resolved it
flows through the same pipeline as chassis and omnipod quirks, and every
derived number picks it up without special-casing.

Two things make skills different from other quirks:

* **Values are scoped.** A structure bonus is nested Faction -> WeightClass ->
  Tonnage, so the same node is worth more on a 100 ton Assault than on a
  20 ton Light. The deepest matching scope wins.
* **Selection is constrained.** Nodes within a branch form a chain, and the
  whole selection is capped at the game's 91 skill points.

A note on the chain rule: the extracted data records each node's grid position
but not the links between them, so MWO's exact prerequisite graph is not
recoverable from it. Every branch does however name its nodes in order
(`Cooldown1` ... `Cooldown16`), and all 48 branches form a clean 1..N run, so
the chain is derived from that ordering: node N requires node N-1 in the same
branch.
"""
import re
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

from omnibay.loader import GameData
from omnibay.quirks import QuirkCollector, finite_number, quirk_value_text
from omnibay.weapons import normalize_lookup_key

# The game's cap on total skill points.
MAX_SKILL_POINTS = 91

_TRAILING_NUMBER = re.compile(r"^(?P<stem>.*?)(?P<order>\d+)$")


def node_stem_and_order(name: str) -> Tuple[str, int]:
    """Split `Cooldown12` into its branch stem and position in the chain.

    Seven nodes carry no number (`AdvancedZoom`, `CoolantReserves`, ...). They
    are single-node branches, so they sit at position 1.
    """
    match = _TRAILING_NUMBER.match(str(name or ""))
    if not match:
        return str(name or ""), 1
    return match.group("stem"), int(match.group("order"))


# --------------------------------------------------------------------------
# Scoped values
# --------------------------------------------------------------------------


def scope_matches(scope: Dict[str, Any], mech: Dict[str, Any]) -> bool:
    scope_type = str(scope.get("type") or "").lower()
    expected = normalize_lookup_key(scope.get("name"))
    if not scope_type or not expected or not mech:
        return False

    if scope_type == "faction":
        faction = str(mech.get("faction") or "").lower()
        normalized = "is" if faction == "innersphere" else normalize_lookup_key(faction)
        return normalized == expected
    if scope_type == "weightclass":
        return normalize_lookup_key(mech.get("weight_class")) == expected
    if scope_type == "tonnage":
        try:
            wanted = float(str(scope.get("name")))
        except (TypeError, ValueError):
            return False
        stats = (mech.get("definition") or {}).get("stats") or {}
        return finite_number(stats.get("MaxTons")) == wanted
    if scope_type == "mech":
        candidates = (mech.get("name"), mech.get("chassis"), mech.get("display_name"))
        return expected in {normalize_lookup_key(c) for c in candidates}
    return False


def resolve_effect_value(effect: Dict[str, Any], mech: Dict[str, Any]) -> float:
    """The value this effect is worth on this mech: deepest matching scope wins."""
    best_depth = 0
    best_value = finite_number(effect.get("value"))

    def visit(scopes: Optional[Iterable[Dict[str, Any]]], depth: int) -> None:
        nonlocal best_depth, best_value
        for scope in scopes or ():
            if not scope_matches(scope, mech):
                continue
            raw = scope.get("value")
            value = best_value if raw is None else finite_number(raw)
            if depth >= best_depth:
                best_depth, best_value = depth, value
            visit(scope.get("children"), depth + 1)

    visit(effect.get("scopes"), 1)
    return best_value


# --------------------------------------------------------------------------
# Requirements
# --------------------------------------------------------------------------


def node_requirements_met(
    data: GameData, node: Dict[str, Any], mech: Dict[str, Any], build: Dict[str, Any]
) -> Tuple[bool, str]:
    """Whether a node applies to this mech, and why not when it does not."""
    from omnibay import build as B
    from omnibay import items as I

    definition = B.effective_definition(data, mech, build)

    for requirement in node.get("requires") or ():
        equipment = requirement.get("equipment")
        if equipment is not None:
            if normalize_lookup_key(equipment) != "jumpjets":
                return False, "Requires {0}".format(equipment)
            stats = (mech.get("definition") or {}).get("stats") or {}
            if int(finite_number(stats.get("MaxJumpJets"))) <= 0:
                return False, "Requires jump jets"
            continue

        hardpoint = requirement.get("hardpoint")
        if hardpoint is not None:
            wanted = normalize_lookup_key(hardpoint)
            present = any(
                normalize_lookup_key(I.hardpoint_type(hp)) == wanted
                for component in (definition.get("components") or {}).values()
                for hp in component.get("hardpoints") or ()
            )
            if not present:
                return False, "Requires a {0} hardpoint".format(hardpoint)
            continue

        return False, "Unsupported requirement"

    for affect in node.get("affects") or ():
        mech_property = affect.get("mechProperty")
        if not mech_property:
            continue
        if normalize_lookup_key(mech_property) == "no360torsotwist":
            if finite_number((definition.get("movement") or {}).get("MaxTorsoAngleYaw")) >= 360:
                return False, "Mech already has 360 degree torso twist"
            continue
        return False, "Unsupported condition"

    return True, ""


# --------------------------------------------------------------------------
# The tree
# --------------------------------------------------------------------------


def build_branches(data: GameData) -> Dict[str, List[Dict[str, Any]]]:
    """Nodes grouped into ordered chains, keyed by category."""
    categories: Dict[str, List[Dict[str, Any]]] = {}
    for category in (data.skills.get("categories") or ()):
        branches: Dict[str, List[Dict[str, Any]]] = {}
        for node in category.get("nodes") or ():
            branches.setdefault(node.get("subcategory") or "", []).append(node)
        ordered = []
        for subcategory, nodes in branches.items():
            nodes = sorted(nodes, key=lambda n: node_stem_and_order(n.get("name"))[1])
            ordered.append({"subcategory": subcategory, "nodes": nodes})
        ordered.sort(key=lambda b: min(n.get("column", 0) for n in b["nodes"]))
        categories[category.get("key") or ""] = ordered
    return categories


def _node_index(data: GameData) -> Dict[str, Dict[str, Any]]:
    index = {}
    for category in (data.skills.get("categories") or ()):
        for node in category.get("nodes") or ():
            index[node["name"]] = node
    return index


def prerequisite_of(data: GameData, name: str) -> Optional[str]:
    """The node that must be taken before this one, if any."""
    node = _node_index(data).get(name)
    if not node:
        return None
    stem, order = node_stem_and_order(name)
    if order <= 1:
        return None
    candidate = "{0}{1}".format(stem, order - 1)
    return candidate if candidate in _node_index(data) else None


def normalize_selection(
    data: GameData, mech: Dict[str, Any], build: Dict[str, Any], selected: Sequence[str]
) -> Tuple[List[str], List[str]]:
    """Return a legal selection, plus the names that had to be dropped.

    Pulls in each node's chain ancestors, drops anything the mech cannot use,
    and truncates to the point cap. Callers can hand in a rough selection and
    trust the result.
    """
    index = _node_index(data)
    wanted = [name for name in dict.fromkeys(selected) if name in index]
    dropped = [name for name in dict.fromkeys(selected) if name not in index]

    # Pull in prerequisites so a selection is always self-consistent.
    resolved: List[str] = []
    seen: Set[str] = set()
    for name in wanted:
        chain: List[str] = []
        cursor: Optional[str] = name
        while cursor and cursor not in seen:
            chain.append(cursor)
            cursor = prerequisite_of(data, cursor)
        for entry in reversed(chain):
            if entry not in seen:
                seen.add(entry)
                resolved.append(entry)

    usable: List[str] = []
    for name in resolved:
        allowed, _reason = node_requirements_met(data, index[name], mech, build)
        if allowed:
            usable.append(name)
        else:
            dropped.append(name)

    if len(usable) > MAX_SKILL_POINTS:
        dropped.extend(usable[MAX_SKILL_POINTS:])
        usable = usable[:MAX_SKILL_POINTS]
    return usable, dropped


def selected_skill_effects(
    data: GameData,
    mech: Dict[str, Any],
    build: Dict[str, Any],
    selected: Optional[Sequence[str]] = None,
) -> List[Dict[str, Any]]:
    """Quirks produced by a skill selection, ready to merge with the rest."""
    names = list(selected or ())
    if not names:
        return []
    index = _node_index(data)
    collector = QuirkCollector()
    for name in dict.fromkeys(names):
        node = index.get(name)
        if not node:
            continue
        allowed, _reason = node_requirements_met(data, node, mech, build)
        if not allowed:
            continue
        for effect in node.get("effects") or ():
            value = resolve_effect_value(effect, mech)
            if not value:
                continue
            collector.add(
                {
                    "name": str(effect.get("name") or "").lower(),
                    "display_name": effect.get("display_name") or effect.get("name"),
                    "value": value,
                },
                "Skills",
                sourceKind="skill",
                skillNode=name,
                skillCategory=node.get("category"),
            )
    return collector.resolve()


def skill_tree(
    data: GameData,
    mech: Dict[str, Any],
    build: Dict[str, Any],
    selected: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    """The whole tree, with per-node values resolved for this mech."""
    chosen = set(selected or ())
    categories_payload = []
    branches_by_category = build_branches(data)

    for category in (data.skills.get("categories") or ()):
        key = category.get("key") or ""
        branch_payload = []
        for branch in branches_by_category.get(key, ()):
            nodes_payload = []
            for position, node in enumerate(branch["nodes"]):
                name = node["name"]
                allowed, reason = node_requirements_met(data, node, mech, build)
                prerequisite = prerequisite_of(data, name)
                effects = []
                for effect in node.get("effects") or ():
                    value = resolve_effect_value(effect, mech)
                    if not value:
                        continue
                    # Named distinctly: `name` above is the node, this is the quirk.
                    effect_name = str(effect.get("name") or "").lower()
                    effects.append(
                        {
                            "name": effect_name,
                            "display_name": effect.get("display_name") or effect.get("name"),
                            "value": value,
                            # Formatted by the engine so `_multiplier` reads as a
                            # percentage and `_additive` as a flat number.
                            "value_text": quirk_value_text(effect_name, value),
                        }
                    )
                nodes_payload.append(
                    {
                        "name": name,
                        "order": position + 1,
                        "column": node.get("column"),
                        "row": node.get("row"),
                        "selected": name in chosen,
                        "available": allowed
                        and (prerequisite is None or prerequisite in chosen),
                        "usable": allowed,
                        "blocked_reason": reason,
                        "requires": prerequisite,
                        "effects": effects,
                    }
                )
            branch_payload.append(
                {
                    "key": "{0}:{1}".format(key, branch["subcategory"]),
                    "subcategory": branch["subcategory"],
                    "label": _humanise(branch["subcategory"]),
                    "nodes": nodes_payload,
                }
            )
        categories_payload.append(
            {"key": key, "name": category.get("name") or key, "branches": branch_payload}
        )

    return {
        "max_points": MAX_SKILL_POINTS,
        "spent": len(chosen),
        "categories": categories_payload,
        "effects": selected_skill_effects(data, mech, build, sorted(chosen)),
    }


def _humanise(subcategory: str) -> str:
    """`MagazineCapacity` -> `Magazine Capacity`, for branch headings."""
    return re.sub(r"(?<!^)(?=[A-Z])", " ", str(subcategory or "")).strip()
