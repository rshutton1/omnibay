"""Loads the extracted MWO game data and builds the lookup indexes.

The JSON under `backend/data/` is produced by the extraction scripts that read a
local MechWarrior Online install. It is treated as immutable reference data:
loaded once at startup, never mutated.
"""
import json
import os
from functools import lru_cache
from typing import Any, Dict, Iterable, List, Optional

from omnibay.constants import COMPONENT_ORDER

# Repository layout: <root>/engine/omnibay/loader.py -> <root>/data
_DEFAULT_DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data"
)


def _read_json(directory: str, filename: str) -> Any:
    path = os.path.join(directory, filename)
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _read_optional_json(directory: str, filename: str, fallback: Any) -> Any:
    """Read a file the engine can work without.

    The browser bundle ships only the files the app actually reads, so
    localization and skill data may legitimately be absent.
    """
    try:
        return _read_json(directory, filename)
    except (IOError, OSError):
        return fallback


# Each upgrade category is recognised by the stat key its items define.
_UPGRADE_CATEGORY_STAT = {
    "armor": "armorPerTon",
    "structure": "weightPerTon",
    "heatsinks": "compatibleHeatSink",
    "guidance": "extraSlots",
}


def _normalize_faction(value: Any) -> str:
    text = str(value or "").strip().lower().replace(" ", "").replace("_", "")
    if text in ("clan", "clans"):
        return "clan"
    if text in ("innersphere", "is"):
        return "innersphere"
    return text


class GameData:
    """In-memory view of the extracted game data with the indexes the engine needs."""

    def __init__(self, data_dir: Optional[str] = None) -> None:
        self.data_dir = data_dir or os.environ.get("OMNIBAY_DATA_DIR") or _DEFAULT_DATA_DIR

        self.index: Dict[str, Any] = _read_json(self.data_dir, "index.json")

        equipment = _read_json(self.data_dir, "equipment.json")
        self.items: Dict[int, Dict[str, Any]] = {
            int(key): value for key, value in equipment["items"].items()
        }
        # `families` maps a family name to the item ids belonging to it.
        self.families: Dict[str, List[int]] = {
            str(name): [int(item_id) for item_id in ids]
            for name, ids in (equipment.get("families") or {}).items()
        }

        self.mechs: List[Dict[str, Any]] = _read_json(self.data_dir, "mechs.json")
        self.mechs_by_id: Dict[int, Dict[str, Any]] = {
            int(mech["id"]): mech for mech in self.mechs
        }
        self.mechs_by_name: Dict[str, Dict[str, Any]] = {
            str(mech["name"]).lower(): mech for mech in self.mechs
        }

        self.omnipods: Dict[int, Dict[str, Any]] = {
            int(key): value for key, value in _read_json(self.data_dir, "omnipods.json").items()
        }
        self.loadouts: Dict[str, Dict[str, Any]] = {
            str(key).lower(): value
            for key, value in _read_json(self.data_dir, "loadouts.json").items()
        }
        self.localization: Dict[str, str] = _read_optional_json(
            self.data_dir, "localization.json", {}
        )
        self.skills: Dict[str, Any] = _read_optional_json(self.data_dir, "skills.json", {})
        # Node layout and prerequisites; see engine/tools/build_skill_graph.py.
        self.skill_graph: Dict[str, Any] = _read_optional_json(
            self.data_dir, "skill-graph.json", {"nodes": {}, "edges": []}
        )
        self.shake_damping_mechs = _read_optional_json(
            self.data_dir, "shake_damping_mechs.json", []
        )

        self._build_secondary_indexes()

    # -- indexes -----------------------------------------------------------

    def _build_secondary_indexes(self) -> None:
        self.items_by_type: Dict[str, List[Dict[str, Any]]] = {}
        for item in self.items.values():
            self.items_by_type.setdefault(str(item.get("item_type") or ""), []).append(item)

        # Omnipods grouped by the chassis they belong to, then by component slot.
        self.omnipods_by_chassis: Dict[str, List[Dict[str, Any]]] = {}
        for pod in self.omnipods.values():
            chassis = str(pod.get("chassis") or "").lower()
            self.omnipods_by_chassis.setdefault(chassis, []).append(pod)

        self.chassis_variants: Dict[str, List[Dict[str, Any]]] = {}
        for mech in self.mechs:
            chassis = str(mech.get("chassis") or "").lower()
            self.chassis_variants.setdefault(chassis, []).append(mech)

        self.engines_by_rating: Dict[int, List[Dict[str, Any]]] = {}
        for engine in self.items_by_type.get("engine", ()):
            rating = int(engine.get("stats", {}).get("rating") or 0)
            self.engines_by_rating.setdefault(rating, []).append(engine)

    # -- lookups -----------------------------------------------------------

    def item(self, item_id: Any) -> Optional[Dict[str, Any]]:
        try:
            return self.items.get(int(item_id))
        except (TypeError, ValueError):
            return None

    def mech(self, mech_id: Any) -> Optional[Dict[str, Any]]:
        try:
            return self.mechs_by_id.get(int(mech_id))
        except (TypeError, ValueError):
            return self.mechs_by_name.get(str(mech_id).lower())

    def mech_by_name(self, name: Any) -> Optional[Dict[str, Any]]:
        return self.mechs_by_name.get(str(name or "").lower())

    def omnipod(self, pod_id: Any) -> Optional[Dict[str, Any]]:
        try:
            return self.omnipods.get(int(pod_id))
        except (TypeError, ValueError):
            return None

    def loadout(self, name: Any) -> Optional[Dict[str, Any]]:
        return self.loadouts.get(str(name or "").lower())

    def stock_loadout_for(self, mech: Dict[str, Any]) -> Dict[str, Any]:
        """Variants name their stock loadout explicitly; it is not always the variant name."""
        return self.loadout(mech.get("stock_loadout") or mech.get("name")) or {}

    def find_omnipod(
        self, chassis: Any, set_name: Any, component: Any
    ) -> Optional[Dict[str, Any]]:
        """Resolve a pod by chassis/set/component. Ambiguous matches resolve to None."""
        wanted_set = str(set_name or "").lower()
        wanted_component = str(component or "").lower()
        matches = [
            pod
            for pod in self.omnipods_for(chassis)
            if str(pod.get("set") or "").lower() == wanted_set
            and str(pod.get("component") or "").lower() == wanted_component
        ]
        return matches[0] if len(matches) == 1 else None

    def items_of_type(self, item_type: str) -> List[Dict[str, Any]]:
        return list(self.items_by_type.get(item_type, ()))

    def upgrade_items(self, category: str) -> List[Dict[str, Any]]:
        """Upgrade items for a category.

        Upgrades carry no explicit type field — each category is identified by
        the stat key it defines, exactly as the reference client does.
        """
        stat_key = _UPGRADE_CATEGORY_STAT.get(str(category or "").lower())
        if stat_key is None:
            return []
        items = [self.item(item_id) for item_id in self.families.get("upgrades", ())]
        return [
            item for item in items if item and stat_key in (item.get("stats") or {})
        ]

    def omnipods_for(self, chassis: Any, component: Optional[str] = None) -> List[Dict[str, Any]]:
        pods = self.omnipods_by_chassis.get(str(chassis or "").lower(), [])
        if component is None:
            return list(pods)
        return [pod for pod in pods if pod.get("component") == component]

    def engines_for_faction(self, faction: Any) -> List[Dict[str, Any]]:
        normalized = _normalize_faction(faction)
        result = []
        for engine in self.items_of_type("engine"):
            factions = [
                _normalize_faction(part) for part in str(engine.get("faction") or "").split(",")
            ]
            if not normalized or normalized in factions:
                result.append(engine)
        return result

    def localize(self, tag: Any, fallback: str = "") -> str:
        key = str(tag or "").lstrip("@")
        return self.localization.get(key, fallback or key)

    # -- metadata ----------------------------------------------------------

    def summary(self) -> Dict[str, Any]:
        return {
            "generated_from": self.index.get("generated_from"),
            "counts": self.index.get("counts"),
            "components": list(COMPONENT_ORDER),
            "families": sorted(self.families),
        }


@lru_cache(maxsize=1)
def get_game_data() -> GameData:
    """Process-wide singleton. FastAPI depends on this."""
    return GameData()


def normalize_faction(value: Any) -> str:
    return _normalize_faction(value)


def iter_component_items(component: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
    return component.get("items") or ()
