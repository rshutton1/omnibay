"""Build state and the loadout calculation engine.

`calculate_build` is the single source of truth for every number the client
shows: tonnage, critical slots, hardpoint usage, armor, heat and the aggregated
quirk list. Ported from `calculateBuild` and its helpers in the reference
client's `public/app.js`.
"""
import math
from typing import Any, Dict, List, Optional, Tuple

from omnibay.loader import GameData, normalize_faction
from omnibay import codec
from omnibay import items as I
from omnibay.constants import (
    ACTUATOR_BITS,
    ARMOR_CONTAINER_SLOT_COUNTS,
    COMPONENT_LABELS,
    COMPONENT_ORDER,
    DEFAULT_ARMOR_PER_TON,
    ENGINE_COMPONENTS,
    ENGINE_SIDE_COMPONENTS,
    HAND_ACTUATOR_ID,
    HEAD_MAX_ARMOR,
    JUMP_JET_COMPONENTS,
    LOWER_ARM_ACTUATOR_ID,
    MOVABLE_UPGRADE_SLOT_IDS,
    STEALTH_ARMOR_SLOTS_BY_COMPONENT,
    STRUCTURE_SLOTS_CLAN,
    STRUCTURE_SLOTS_INNER_SPHERE,
    STRUCTURE_SLOT_ORDER,
)
from omnibay.quirks import QuirkCollector, finite_number

# Rear armor is stored in the loadout data as separate pseudo-components.
TORSO_REAR_COMPONENTS = {
    "left_torso": "left_torso_rear",
    "centre_torso": "centre_torso_rear",
    "right_torso": "right_torso_rear",
}

# --------------------------------------------------------------------------
# Build state
# --------------------------------------------------------------------------


def empty_build() -> Dict[str, Any]:
    """A build with no equipment, no armor and standard upgrades."""
    return {
        "components": {
            name: {"armor": 0, "rear_armor": 0, "omnipod": None, "items": []}
            for name in COMPONENT_ORDER
        },
        "upgrades": {
            "armor": None,
            "structure": None,
            "heatsinks": None,
            "artemis": False,
        },
        "engine_heat_sinks": [],
        "actuator_state": 0,
    }


def build_from_stock_loadout(data: GameData, mech: Dict[str, Any]) -> Dict[str, Any]:
    """Seed a build from the variant's stock loadout as shipped by the game."""
    build = empty_build()
    loadout = data.stock_loadout_for(mech)
    if not loadout:
        return build

    upgrades = loadout.get("upgrades") or {}
    for category in ("armor", "structure", "heatsinks"):
        build["upgrades"][category] = _loadout_upgrade_id(upgrades.get(category))
    build["upgrades"]["artemis"] = bool((upgrades.get("artemis") or {}).get("Equipped"))

    loadout_components = loadout.get("components") or {}
    for name, component in loadout_components.items():
        if name not in build["components"]:
            continue
        target = build["components"][name]
        target["armor"] = int(finite_number(component.get("armor")))
        target["omnipod"] = component.get("omnipod")
        target["items"] = [
            {"item_id": entry.get("item_id"), "weapon_group": entry.get("weapon_group")}
            for entry in (component.get("items") or [])
            if entry.get("item_id") is not None
        ]

    for name, rear_name in TORSO_REAR_COMPONENTS.items():
        rear = loadout_components.get(rear_name) or {}
        build["components"][name]["rear_armor"] = max(
            0, int(finite_number(rear.get("armor")))
        )
    # Omnimechs ship with both lower arm actuators removed.
    build["actuator_state"] = (
        ACTUATOR_BITS["left_lower_arm_removed"] | ACTUATOR_BITS["right_lower_arm_removed"]
        if has_fixed_omnipods(data, mech)
        else 0
    )
    return apply_fixed_omnipods(data, mech, build, migrate_engine_heat_sinks=True)


def _loadout_upgrade_id(entry: Optional[Dict[str, Any]]) -> Optional[int]:
    """Read an upgrade id from a stock loadout.

    A handful of extracted variants (VTR-9SC) spell the key `ItemId`, so both
    casings are accepted rather than silently dropping the upgrade.
    """
    if not entry:
        return None
    for key in ("ItemID", "ItemId", "itemId", "itemID"):
        if key in entry:
            try:
                return int(entry[key])
            except (TypeError, ValueError):
                return None
    return None


def has_fixed_omnipods(data: GameData, mech: Dict[str, Any]) -> bool:
    """Omnimechs ship with omnipods pinned in their stock loadout.

    The extracted data writes the literal string "none" for battlemechs, so the
    value must be parsed as an id rather than merely tested for truthiness.
    """
    loadout = data.stock_loadout_for(mech)
    return any(
        _omnipod_id(component.get("omnipod"))
        for component in (loadout.get("components") or {}).values()
    )


# --------------------------------------------------------------------------
# Effective definition (chassis + omnipods)
# --------------------------------------------------------------------------


def effective_component_definition(
    data: GameData, mech: Dict[str, Any], build: Dict[str, Any], component_name: str
) -> Dict[str, Any]:
    """Merge the chassis component with whatever omnipod is installed in it."""
    base = ((mech.get("definition") or {}).get("components") or {}).get(component_name) or {}
    build_component = (build.get("components") or {}).get(component_name) or {}
    pod = data.omnipod(build_component.get("omnipod"))

    if pod:
        hardpoints = list(pod.get("hardpoints") or [])
        pod_internals = list(pod.get("internals") or [])
        pod_fixed = list(pod.get("fixed") or [])
    else:
        hardpoints = list(base.get("hardpoints") or [])
        pod_internals = []
        pod_fixed = []

    hardpoints = [
        dict(hardpoint, hardpoint_type=I.hardpoint_type(hardpoint)) for hardpoint in hardpoints
    ]

    internals = [
        item_id
        for item_id in list(base.get("internals") or []) + pod_internals
        if not actuator_is_removed(component_name, item_id, build)
    ]

    base_fixed = list(base.get("fixed") or [])
    return {
        **base,
        "hardpoints": hardpoints,
        "internals": internals,
        "fixed": base_fixed + pod_fixed,
        "fixed_sources": ["chassis"] * len(base_fixed) + ["omnipod"] * len(pod_fixed),
    }


def actuator_is_removed(component_name: str, item_id: Any, build: Dict[str, Any]) -> bool:
    """Arm actuators can be stripped; removing the lower arm removes the hand too."""
    state = max(0, int(finite_number((build or {}).get("actuator_state"))))
    try:
        numeric_id = int(item_id)
    except (TypeError, ValueError):
        return False

    if component_name == "left_arm":
        if numeric_id == LOWER_ARM_ACTUATOR_ID:
            return bool(state & ACTUATOR_BITS["left_lower_arm_removed"])
        if numeric_id == HAND_ACTUATOR_ID:
            return bool(
                state
                & (ACTUATOR_BITS["left_lower_arm_removed"] | ACTUATOR_BITS["left_hand_removed"])
            )
    if component_name == "right_arm":
        if numeric_id == LOWER_ARM_ACTUATOR_ID:
            return bool(state & ACTUATOR_BITS["right_lower_arm_removed"])
        if numeric_id == HAND_ACTUATOR_ID:
            return bool(
                state
                & (ACTUATOR_BITS["right_lower_arm_removed"] | ACTUATOR_BITS["right_hand_removed"])
            )
    return False


def structure_upgrade_tonnage(max_tons: Any, upgrade: Optional[Dict[str, Any]]) -> float:
    """Internal structure weight, rounded up to the nearest half ton."""
    weight_per_ton = max(
        0.0, finite_number((upgrade or {}).get("stats", {}).get("weightPerTon"), 0.1)
    )
    raw = max(0.0, finite_number(max_tons)) * weight_per_ton
    return math.ceil(raw * 2) / 2


def effective_definition(
    data: GameData, mech: Dict[str, Any], build: Dict[str, Any]
) -> Dict[str, Any]:
    definition = mech.get("definition") or {}
    components = {
        name: effective_component_definition(data, mech, build, name)
        for name in (definition.get("components") or {})
    }
    return {**definition, "components": components}


def effective_quirks(
    data: GameData, mech: Dict[str, Any], build: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """Chassis quirks, plus installed omnipod quirks, plus any earned set bonuses."""
    collector = QuirkCollector()
    definition = mech.get("definition") or {}
    for quirk in definition.get("quirks") or ():
        collector.add(quirk, "Variant", sourceKind="variant")

    set_counts: Dict[str, int] = {}
    set_bonuses: Dict[str, List[Dict[str, Any]]] = {}
    for component, build_component in (build.get("components") or {}).items():
        pod = data.omnipod(build_component.get("omnipod"))
        if not pod:
            continue
        label = COMPONENT_LABELS.get(component, "Omnipod")
        for quirk in pod.get("quirks") or ():
            collector.add(
                quirk,
                label,
                sourceKind="fixedCt" if component == "centre_torso" else "omnipod",
                component=component,
                podId=pod.get("id"),
            )
        pod_set = pod.get("set")
        if pod_set:
            set_counts[pod_set] = set_counts.get(pod_set, 0) + 1
            set_bonuses[pod_set] = pod.get("set_bonuses") or []

    for set_name, count in set_counts.items():
        for bonus in set_bonuses.get(set_name) or ():
            piece_count = int(finite_number(bonus.get("piece_count")))
            if count >= piece_count:
                source = "{0} {1}pc".format(str(set_name).upper(), piece_count)
                for quirk in bonus.get("quirks") or ():
                    collector.add(
                        quirk,
                        source,
                        sourceKind="setBonus",
                        setName=set_name,
                        pieceCount=piece_count,
                    )

    return collector.resolve()


# --------------------------------------------------------------------------
# Engines and upgrades
# --------------------------------------------------------------------------


def fixed_omni_engine(data: GameData, mech: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Omnimechs have a welded-in engine, identified by min rating == max rating."""
    if not has_fixed_omnipods(data, mech):
        return None
    stats = (mech.get("definition") or {}).get("stats") or {}
    min_rating = int(finite_number(stats.get("MinEngineRating")))
    max_rating = int(finite_number(stats.get("MaxEngineRating")))
    if not min_rating or min_rating != max_rating:
        return None

    for component in ((mech.get("definition") or {}).get("components") or {}).values():
        for item_id in component.get("fixed") or ():
            item = data.item(item_id)
            if I.is_engine(item):
                return item

    faction = normalize_faction(mech.get("faction"))
    expected_side_slots = 2 if faction == "clan" else 3 if faction == "innersphere" else -1
    for engine in data.engines_for_faction(faction):
        if (
            I.engine_rating(engine) == min_rating
            and I.engine_side_slots(engine) == expected_side_slots
        ):
            return engine
    return None


def installed_engine(
    data: GameData, mech: Dict[str, Any], build: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    fixed = fixed_omni_engine(data, mech)
    if fixed:
        return fixed
    for component in (build.get("components") or {}).values():
        for entry in component.get("items") or ():
            item = data.item(entry.get("item_id"))
            if I.is_engine(item):
                return item
    return None


def guidance_upgrade(data: GameData, build: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Artemis and standard guidance are two items; pick the one matching the toggle."""
    wants_artemis = bool((build.get("upgrades") or {}).get("artemis"))
    for item in data.upgrade_items("guidance"):
        has_extra = finite_number((item.get("stats") or {}).get("extraSlots")) > 0
        if has_extra == wants_artemis:
            return item
    return None


def effective_item_slots(
    data: GameData, item: Optional[Dict[str, Any]], build: Dict[str, Any]
) -> int:
    """Artemis adds a critical slot to each guided missile launcher."""
    extra = 0
    if I.is_artemis_weapon(item) and (build.get("upgrades") or {}).get("artemis"):
        upgrade = guidance_upgrade(data, build)
        extra = int(finite_number((upgrade or {}).get("stats", {}).get("extraSlots")))
    return I.item_slots(item) + extra


def structure_upgrade_slots(
    data: GameData, mech: Dict[str, Any], build: Dict[str, Any]
) -> int:
    """Endo-steel costs 7 slots for Clan, 14 for Inner Sphere. Omnimechs pay none."""
    if has_fixed_omnipods(data, mech):
        return 0
    upgrade = data.item((build.get("upgrades") or {}).get("structure"))
    if not upgrade:
        return 0
    if finite_number((upgrade.get("stats") or {}).get("weightPerTon"), 0.1) >= 0.1:
        return 0
    return (
        STRUCTURE_SLOTS_CLAN
        if normalize_faction(mech.get("faction")) == "clan"
        else STRUCTURE_SLOTS_INNER_SPHERE
    )


def armor_upgrade_slots(data: GameData, mech: Dict[str, Any], build: Dict[str, Any]) -> int:
    if has_fixed_omnipods(data, mech):
        return 0
    upgrade = data.item((build.get("upgrades") or {}).get("armor"))
    if not upgrade:
        return 0
    if "stealth" in str(upgrade.get("name") or "").lower():
        return sum(STEALTH_ARMOR_SLOTS_BY_COMPONENT.values())
    container_id = int(finite_number((upgrade.get("stats") or {}).get("containerId")))
    return ARMOR_CONTAINER_SLOT_COUNTS.get(container_id, 0)


def fixed_armor_upgrade_slots(
    data: GameData, mech: Dict[str, Any], build: Dict[str, Any]
) -> Dict[str, int]:
    """Stealth armor pins its slots to specific components instead of floating."""
    if has_fixed_omnipods(data, mech):
        return {}
    upgrade = data.item((build.get("upgrades") or {}).get("armor"))
    if not upgrade or "stealth" not in str(upgrade.get("name") or "").lower():
        return {}
    return dict(STEALTH_ARMOR_SLOTS_BY_COMPONENT)


def armor_tonnage(armor_points: Any, armor_upgrade: Optional[Dict[str, Any]]) -> float:
    per_ton = finite_number(
        (armor_upgrade or {}).get("stats", {}).get("armorPerTon"), DEFAULT_ARMOR_PER_TON
    )
    if per_ton <= 0:
        return 0.0
    return max(0.0, finite_number(armor_points)) / per_ton


def base_max_armor(mech: Dict[str, Any], component_name: str) -> int:
    """Armor cap is twice internal HP, except the head which is fixed at 18."""
    if component_name == "head":
        return HEAD_MAX_ARMOR
    components = (mech.get("definition") or {}).get("components") or {}
    return int(finite_number((components.get(component_name) or {}).get("hp"))) * 2


# --------------------------------------------------------------------------
# Slot allocation
# --------------------------------------------------------------------------


def component_base_slot_usage(
    data: GameData,
    name: str,
    definition: Dict[str, Any],
    build: Dict[str, Any],
    engine: Optional[Dict[str, Any]],
    fixed_engine: Optional[Dict[str, Any]],
) -> int:
    """Slots consumed before any floating upgrade slots are placed."""
    comp_def = (definition.get("components") or {}).get(name) or {}
    build_comp = (build.get("components") or {}).get(name) or {}

    internal_slots = 0
    for item_id in comp_def.get("internals") or ():
        if int(finite_number(item_id)) in MOVABLE_UPGRADE_SLOT_IDS:
            continue
        internal_slots += max(1, I.item_slots(data.item(item_id)))

    fixed_slots = 0
    for item_id in comp_def.get("fixed") or ():
        item = data.item(item_id)
        if not item or I.is_engine(item):
            continue
        if name == "centre_torso" and I.is_heat_sink(item):
            continue
        fixed_slots += max(1, effective_item_slots(data, item, build))

    side_engine_slots = I.engine_side_slots(engine) if name in ENGINE_SIDE_COMPONENTS else 0
    fixed_engine_slots = (
        max(1, I.item_slots(fixed_engine)) if name == "centre_torso" and fixed_engine else 0
    )

    equipment_slots = 0
    for entry in build_comp.get("items") or ():
        item = data.item(entry.get("item_id"))
        if item:
            equipment_slots += max(1, effective_item_slots(data, item, build))

    return (
        internal_slots
        + fixed_slots
        + side_engine_slots
        + fixed_engine_slots
        + equipment_slots
    )


def allocate_upgrade_slots(
    data: GameData,
    required_slots: int,
    definition: Dict[str, Any],
    build: Dict[str, Any],
    engine: Optional[Dict[str, Any]],
    fixed_engine: Optional[Dict[str, Any]],
    reserved_by_component: Optional[Dict[str, int]] = None,
) -> Tuple[Dict[str, int], int]:
    """Spread floating upgrade slots over components in the game's fill order.

    Returns `(by_component, unallocated)`.
    """
    reserved_by_component = reserved_by_component or {}
    by_component: Dict[str, int] = {}
    remaining = required_slots
    for name in STRUCTURE_SLOT_ORDER:
        slot_limit = int(finite_number(((definition.get("components") or {}).get(name) or {}).get("slots")))
        available = max(
            0,
            slot_limit
            - component_base_slot_usage(data, name, definition, build, engine, fixed_engine)
            - int(finite_number(reserved_by_component.get(name))),
        )
        allocated = min(available, remaining)
        by_component[name] = allocated
        remaining -= allocated
    return by_component, remaining


def allocate_fixed_upgrade_slots(fixed_by_component: Dict[str, int]) -> Tuple[Dict[str, int], int]:
    """Stealth armor slots are pinned, so allocation is just the fixed mapping."""
    return dict(fixed_by_component), 0


# --------------------------------------------------------------------------
# Normalization
# --------------------------------------------------------------------------


def fixed_engine_heat_sink_items(
    data: GameData, mech: Dict[str, Any], build: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """Heat sinks welded into the centre torso by the chassis or its omnipod.

    They occupy engine bay capacity, so fewer user heat sinks fit inside.
    """
    centre_base = ((mech.get("definition") or {}).get("components") or {}).get(
        "centre_torso"
    ) or {}
    centre_build = (build.get("components") or {}).get("centre_torso") or {}
    pod = data.omnipod(centre_build.get("omnipod"))
    pod_fixed = list((pod or {}).get("fixed") or [])

    entries = []
    for item_id in list(centre_base.get("fixed") or []) + pod_fixed:
        item = data.item(item_id)
        if I.is_heat_sink(item):
            entries.append(item)
    return entries


def engine_stored_heat_sink_capacity(
    data: GameData,
    mech: Dict[str, Any],
    build: Dict[str, Any],
    engine: Optional[Dict[str, Any]] = None,
) -> int:
    """How many user heat sinks the engine bay can hold, after fixed ones."""
    if engine is None:
        engine = installed_engine(data, mech, build)
    return max(
        0,
        I.engine_additional_heat_sink_capacity(engine)
        - len(fixed_engine_heat_sink_items(data, mech, build)),
    )


def normalize_engine_heat_sinks(
    data: GameData,
    mech: Dict[str, Any],
    build: Dict[str, Any],
    fill_from_centre: bool = False,
) -> Dict[str, Any]:
    """Move heat sinks between the centre torso and the engine bay.

    Heat sinks inside the engine cost tonnage but no critical slots, so the
    reference client keeps the bay filled first and spills the rest back into
    the centre torso.
    """
    components = build.setdefault("components", {})
    centre = components.setdefault("centre_torso", {"armor": 0, "rear_armor": 0, "items": []})
    centre_items = centre.setdefault("items", [])

    engine = installed_engine(data, mech, build)
    capacity = engine_stored_heat_sink_capacity(data, mech, build, engine)

    internal: List[Dict[str, Any]] = []
    overflow: List[Dict[str, Any]] = []
    for entry in build.get("engine_heat_sinks") or ():
        item = data.item(entry.get("item_id") if isinstance(entry, dict) else entry)
        if I.is_heat_sink(item):
            internal.append(dict(entry) if isinstance(entry, dict) else {"item_id": entry})
        elif entry:
            overflow.append(dict(entry) if isinstance(entry, dict) else {"item_id": entry})

    if fill_from_centre and capacity > len(internal):
        index = 0
        while index < len(centre_items) and len(internal) < capacity:
            entry = centre_items[index]
            if I.is_heat_sink(data.item(entry.get("item_id"))):
                internal.append(centre_items.pop(index))
                continue
            index += 1

    if len(internal) > capacity:
        overflow.extend(internal[capacity:])
        internal = internal[:capacity]

    build["engine_heat_sinks"] = internal
    centre_items.extend(overflow)
    return build


def apply_fixed_omnipods(
    data: GameData,
    mech: Dict[str, Any],
    build: Dict[str, Any],
    migrate_engine_heat_sinks: bool = False,
) -> Dict[str, Any]:
    """Fill in an omnimech's stock pods and drop any engine the chassis welds in."""
    loadout = data.stock_loadout_for(mech)
    loadout_components = loadout.get("components") or {}
    is_omni = has_fixed_omnipods(data, mech)

    components = build.setdefault("components", {})
    for name in COMPONENT_ORDER:
        component = components.setdefault(
            name, {"armor": 0, "rear_armor": 0, "omnipod": None, "items": []}
        )
        component["omnipod"] = _omnipod_id(component.get("omnipod"))
        if not component["omnipod"]:
            stock_pod = _omnipod_id((loadout_components.get(name) or {}).get("omnipod"))
            if stock_pod:
                component["omnipod"] = stock_pod

    if fixed_omni_engine(data, mech):
        for component in components.values():
            component["items"] = [
                entry
                for entry in component.get("items") or ()
                if not I.is_engine(data.item(entry.get("item_id")))
            ]

    centre = components.get("centre_torso") or {}
    if is_omni and not centre.get("omnipod"):
        pod = data.find_omnipod(
            mech.get("chassis"), mech.get("stock_loadout") or mech.get("name"), "centre_torso"
        )
        if pod:
            centre["omnipod"] = pod.get("id")

    return normalize_engine_heat_sinks(
        data, mech, build, fill_from_centre=migrate_engine_heat_sinks
    )


def _omnipod_id(value: Any) -> Optional[int]:
    try:
        numeric = int(value)
    except (TypeError, ValueError):
        return None
    return numeric if numeric > 0 else None


# --------------------------------------------------------------------------
# MWO loadout codes
# --------------------------------------------------------------------------

# The wire format stores upgrades as small integers; these are the item ids
# each value maps to.
MWO_UPGRADE_IDS: Dict[str, Dict[int, int]] = {
    "armor": {0: 2810, 1: 2811, 2: 2812, 3: 2814, 4: 2815, 5: 2816},
    "structure": {0: 3100, 1: 3101, 2: 3102, 3: 3103},
    "heatsinks": {0: 3003, 1: 3002, 2: 3005, 3: 3006},
}
MWO_UPGRADE_BITS: Dict[str, Dict[int, int]] = {
    category: {item_id: bits for bits, item_id in mapping.items()}
    for category, mapping in MWO_UPGRADE_IDS.items()
}


def _mwo_upgrade_id(data: GameData, category: str, bits: Any, mech: Dict[str, Any]) -> Optional[int]:
    item_id = MWO_UPGRADE_IDS.get(category, {}).get(int(finite_number(bits)))
    if item_id and data.item(item_id):
        return item_id
    # Fall back to whatever the variant ships with.
    stock = (data.stock_loadout_for(mech).get("upgrades") or {}).get(category) or {}
    return stock.get("ItemID")


def _mwo_upgrade_bits(category: str, item_id: Any) -> int:
    try:
        bits = MWO_UPGRADE_BITS[category][int(item_id)]
    except (KeyError, TypeError, ValueError):
        raise codec.MwoCodecError(
            "Unsupported {0} upgrade ID: {1}".format(category, item_id)
        )
    return bits


def build_from_decoded_code(
    data: GameData, mech: Dict[str, Any], decoded: Dict[str, Any]
) -> Dict[str, Any]:
    """Turn a decoded MWO loadout code into a build, validating ids as it goes."""
    is_omni = bool(decoded.get("is_omni"))
    build = empty_build()

    for name in COMPONENT_ORDER:
        source = (decoded.get("components") or {}).get(name) or {}
        pod_id = None
        if is_omni and name != "centre_torso":
            pod_id = _omnipod_id(source.get("omnipod"))
            pod = data.omnipod(pod_id)
            if (
                not pod
                or str(pod.get("chassis") or "").lower() != str(mech.get("chassis") or "").lower()
                or str(pod.get("component") or "").lower() != name
            ):
                raise codec.MwoCodecError(
                    "Invalid omnipod {0} for {1}".format(source.get("omnipod"), name)
                )

        items = []
        for item_id in source.get("item_ids") or ():
            item = data.item(item_id)
            if not item:
                raise codec.MwoCodecError("Unknown item id: {0}".format(item_id))
            items.append({"item_id": item["id"], "weapon_group": None})

        build["components"][name] = {
            "armor": max(0, int(finite_number(source.get("armor")))),
            "rear_armor": 0,
            "omnipod": pod_id,
            "items": items,
        }

    for name in TORSO_REAR_COMPONENTS:
        build["components"][name]["rear_armor"] = max(
            0, int(finite_number((decoded.get("rear_armor") or {}).get(name)))
        )

    upgrades = decoded.get("upgrades") or {}
    build["upgrades"] = {
        "armor": _mwo_upgrade_id(data, "armor", upgrades.get("armor_type"), mech),
        "structure": _mwo_upgrade_id(data, "structure", upgrades.get("structure_type"), mech),
        "heatsinks": _mwo_upgrade_id(data, "heatsinks", upgrades.get("heat_sink_type"), mech),
        "artemis": bool(upgrades.get("artemis")),
    }
    build["actuator_state"] = (
        max(0, int(finite_number(decoded.get("actuator_state")))) if is_omni else 0
    )
    return apply_fixed_omnipods(data, mech, build, migrate_engine_heat_sinks=True)


def build_to_mwo_code(data: GameData, mech: Dict[str, Any], build: Dict[str, Any]) -> str:
    """Serialize a build to an MWO loadout code the game itself accepts."""
    is_omni = has_fixed_omnipods(data, mech)
    upgrades = build.get("upgrades") or {}

    components: Dict[str, Any] = {}
    for name in COMPONENT_ORDER:
        component = (build.get("components") or {}).get(name) or {}
        item_ids = [
            int(entry.get("item_id"))
            for entry in component.get("items") or ()
            if entry.get("item_id") is not None
        ]
        if name == "centre_torso":
            # Heat sinks stored in the engine bay ride along in the centre torso.
            item_ids.extend(
                int(entry.get("item_id"))
                for entry in build.get("engine_heat_sinks") or ()
                if entry.get("item_id") is not None
            )
        components[name] = {
            "armor": max(0, int(finite_number(component.get("armor")))),
            "omnipod": component.get("omnipod") or None,
            "item_ids": item_ids,
        }

    loadout = {
        "chassis_id": mech.get("id"),
        "is_omni": is_omni,
        "actuator_state": max(0, int(finite_number(build.get("actuator_state")))) if is_omni else 0,
        "upgrades": {
            "armor_type": _mwo_upgrade_bits("armor", upgrades.get("armor")),
            "structure_type": _mwo_upgrade_bits("structure", upgrades.get("structure")),
            "heat_sink_type": _mwo_upgrade_bits("heatsinks", upgrades.get("heatsinks")),
            "artemis": bool(upgrades.get("artemis")),
        },
        "components": components,
        "rear_armor": {
            name: max(
                0,
                int(finite_number(((build.get("components") or {}).get(name) or {}).get("rear_armor"))),
            )
            for name in TORSO_REAR_COMPONENTS
        },
    }
    return codec.encode(loadout)
