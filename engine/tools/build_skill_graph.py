"""Generate `data/skill-graph.json`: node layout, display labels and prerequisites.

The game extract in `data/skills.json` gives every node's effects, its grid
column/row and an internal name, but *not* the links between nodes. Without
those, prerequisites can only be guessed at, and guessing gets it wrong: the
real tree has cross-branch edges (Kinetic Burst 4 unlocks Speed Tweak 1) that no
per-branch rule can express.

This file supplies what the extract lacks. The layout and edges were read off
the rendered skill tree at https://www.mwoskilltree.com/skilltree, which draws
MechWarrior Online's real tree; the topology is a fact about the game rather
than anything invented there. Regenerate by re-reading that page's node
positions and SVG connectors and updating NODES/EDGES below.

The extract also names a few branches differently from the game. Most notably
`ShockAbsorbance` in our data is the *survival* skill the game calls "Overheat
Damage", while the game's "Shock Absorbance" is the *jump jet* fall-damage skill
our data calls `Vectoring`. LABEL_ALIASES maps the game's display names onto our
internal ones; effects were used to confirm each pairing.
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SOURCE = "https://www.mwoskilltree.com/skilltree"

# Game display name -> the branch name used in data/skills.json.
LABEL_ALIASES = {
    "Overheat Damage": "ShockAbsorbance",
    "Shock Absorbance": "Vectoring",
    "Enhanced UAC/RAC": "UACJamChance",
    "Thermal Cycling": "FlamerVentilation",
    "Adv. Salvos": "ExtendedBombardment",
    "Enhanced ECM Systems": "EnhancedECM",
    "Enhanced Narc": "EnhancedNARC",
    "UAV Duration": "UAVTime",
}

_TRAILING_NUMBER = re.compile(r"^(?P<stem>.*?)\s*(?P<order>\d+)$")


def internal_name(label: str) -> str:
    """`Overheat Damage 3` -> `ShockAbsorbance3`."""
    match = _TRAILING_NUMBER.match(label.strip())
    stem, order = (match.group("stem"), match.group("order")) if match else (label.strip(), "")
    stem = LABEL_ALIASES.get(stem, stem)
    return "{0}{1}".format(re.sub(r"[^A-Za-z0-9]", "", stem), order)


def branch_label(label: str) -> str:
    """The game's own branch heading, without the node number."""
    match = _TRAILING_NUMBER.match(label.strip())
    return (match.group("stem") if match else label).strip()


def main() -> int:
    here = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(here, "skill_graph_source.txt"), encoding="utf-8") as handle:
        raw_nodes, raw_edges = handle.read().split("---EDGES---")

    with open(os.path.join(ROOT, "data", "skills.json"), encoding="utf-8") as handle:
        skills = json.load(handle)
    known = {
        node["name"]: category["key"]
        for category in skills["categories"]
        for node in category["nodes"]
    }

    nodes, unknown = {}, []
    for entry in raw_nodes.strip().split(";"):
        if not entry.strip():
            continue
        label, x, y = entry.rsplit("|", 2)
        name = internal_name(label)
        if name not in known:
            unknown.append((label, name))
            continue
        nodes[name] = {
            "label": label.strip(),
            "branch": branch_label(label),
            "category": known[name],
            "x": int(x),
            "y": int(y),
        }

    edges, dangling = [], []
    for entry in raw_edges.strip().split(";"):
        if not entry.strip():
            continue
        source, target = entry.split(">")
        a, b = internal_name(source), internal_name(target)
        if a in nodes and b in nodes:
            edges.append([a, b])
        else:
            dangling.append(entry)

    if unknown or dangling:
        print("unmapped nodes: {0}".format(unknown[:5]), file=sys.stderr)
        print("dangling edges: {0}".format(dangling[:5]), file=sys.stderr)
        return 1
    if len(nodes) != len(known):
        print(
            "covered {0} of {1} nodes; missing {2}".format(
                len(nodes), len(known), sorted(set(known) - set(nodes))[:8]
            ),
            file=sys.stderr,
        )
        return 1

    out = os.path.join(ROOT, "data", "skill-graph.json")
    with open(out, "w", encoding="utf-8") as handle:
        json.dump({"source": SOURCE, "nodes": nodes, "edges": edges}, handle, indent=1)
    print("skill graph  {0} nodes, {1} edges".format(len(nodes), len(edges)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
