"""Full build calculation.

`calculate_build` walks every component once and produces the complete numeric
picture of a loadout — the thing the mech lab UI renders. Ported from
`calculateBuild` in the reference client's `public/app.js`.
"""
from typing import Any, Dict, List, Optional

from omnibay.loader import GameData
from omnibay import build as B
from omnibay import items as I
from omnibay.constants import (
    COMPONENT_ABBREVIATIONS,
    TONNAGE_EPSILON,
    COMPONENT_LABELS,
    COMPONENT_QUIRK_CODES,
    COMPONENT_ORDER,
    ENGINE_COMPONENTS,
    ENGINE_SIDE_COMPONENTS,
    JUMP_JET_COMPONENTS,
    MOVABLE_UPGRADE_SLOT_IDS,
)
from omnibay import weapons as W
from omnibay import weapon_stats as WS
from omnibay.quirks import (
    durability_skill_final_value,
    finite_number,
    quirk_add,
    quirk_family,
    quirk_multiplier,
    quirk_values,
)


def _round(value: float, places: int = 3) -> float:
    return round(value + 0.0, places)


def calculate_build(
    data: GameData, mech: Dict[str, Any], build: Dict[str, Any]
) -> Dict[str, Any]:
    definition = B.effective_definition(data, mech, build)
    stats = definition.get("stats") or {}
    max_tons = finite_number(stats.get("MaxTons"))

    quirks = B.effective_quirks(data, mech, build)
    quirk_lookup = quirk_values(quirks)

    engine = B.installed_engine(data, mech, build)
    fixed_engine = B.fixed_omni_engine(data, mech)
    armor_upgrade = data.item((build.get("upgrades") or {}).get("armor"))
    guidance = B.guidance_upgrade(data, build)
    guidance_tons = finite_number((guidance or {}).get("stats", {}).get("extraTons"))

    modules = _installed_modules(data, definition, build)

    item_tonnage = I.item_tons(fixed_engine) if fixed_engine else 0.0
    heat = 0.0
    alpha = 0.0
    # Kept so the rate metrics can time every weapon once the heat system is known.
    weapon_items: List[Dict[str, Any]] = []
    ammo_shots = 0.0
    armor_points = 0
    installed_heat_sinks = 0
    warnings: List[str] = []

    # -- upgrade slot allocation ------------------------------------------
    required_structure_slots = B.structure_upgrade_slots(data, mech, build)
    required_armor_slots = B.armor_upgrade_slots(data, mech, build)
    fixed_armor_by_component = B.fixed_armor_upgrade_slots(data, mech, build)
    has_fixed_armor_slots = bool(fixed_armor_by_component)

    # Pinned (stealth) armor slots are reserved before structure is spread.
    structure_by_component, structure_unallocated = B.allocate_upgrade_slots(
        data,
        required_structure_slots,
        definition,
        build,
        engine,
        fixed_engine,
        fixed_armor_by_component,
    )
    if has_fixed_armor_slots:
        armor_by_component, armor_unallocated = B.allocate_fixed_upgrade_slots(
            fixed_armor_by_component
        )
    else:
        armor_by_component, armor_unallocated = B.allocate_upgrade_slots(
            data,
            required_armor_slots,
            definition,
            build,
            engine,
            fixed_engine,
            structure_by_component,
        )

    components: Dict[str, Dict[str, Any]] = {}

    for name in COMPONENT_ORDER:
        comp_def = (definition.get("components") or {}).get(name) or {}
        build_comp = (build.get("components") or {}).get(name) or {"items": []}

        usage: Dict[str, Any] = {
            "name": name,
            "label": COMPONENT_LABELS.get(name, name),
            "abbreviation": COMPONENT_ABBREVIATIONS.get(name, name[:2].upper()),
            "quirks": _component_quirks(quirks, name),
            "slot_limit": int(finite_number(comp_def.get("slots"))),
            "slots": 0,
            "hardpoints": {},
            "hardpoint_capacity": {},
            "armor": max(0, int(finite_number(build_comp.get("armor")))),
            "rear_armor": max(0, int(finite_number(build_comp.get("rear_armor")))),
            "max_armor": B.base_max_armor(mech, name),
            "structure": int(finite_number(comp_def.get("hp"))),
            "omnipod": build_comp.get("omnipod"),
            "items": [],
            "fixed_items": [],
            "internals": [],
            "warnings": [],
        }

        # Internals (cockpit, gyro, actuators) — structural, never removable here.
        internal_slots = 0
        for item_id in comp_def.get("internals") or ():
            item = data.item(item_id)
            if not item:
                continue
            if int(finite_number(item_id)) in MOVABLE_UPGRADE_SLOT_IDS and not B.has_fixed_omnipods(
                data, mech
            ):
                continue
            internal_slots += max(1, I.item_slots(item))
            item_tonnage += I.internal_item_tonnage_modifier(item)
            usage["internals"].append(_describe_item(data, item))

        # Fixed equipment contributed by the chassis or the installed omnipod.
        fixed_slots = 0
        for index, item_id in enumerate(comp_def.get("fixed") or ()):
            item = data.item(item_id)
            if not item or I.is_engine(item):
                continue
            source = (comp_def.get("fixed_sources") or [None] * (index + 1))[index] or ""
            if not (name == "centre_torso" and I.is_heat_sink(item)):
                fixed_slots += max(1, B.effective_item_slots(data, item, build))
            item_tonnage += I.item_tons(item)
            heat += W.weapon_heat(data, item) if I.is_weapon(item) else I.item_heat(item)
            mount = I.equipment_hardpoint_type(item)
            if mount:
                usage["hardpoints"][mount] = usage["hardpoints"].get(mount, 0) + 1
            if I.is_weapon(item) and not I.is_ams_weapon(item):
                alpha += W.weapon_total_damage(data, item, True, modules)
                weapon_items.append(item)
            if I.is_ammo(item):
                ammo_shots += W.effective_ammo_shots(item, quirks)
            if I.is_heat_sink(item):
                installed_heat_sinks += 1
            usage["fixed_items"].append(dict(_describe_item(data, item), source=source))

        side_engine_slots = I.engine_side_slots(engine) if name in ENGINE_SIDE_COMPONENTS else 0
        fixed_engine_slots = (
            max(1, I.item_slots(fixed_engine))
            if name == "centre_torso" and fixed_engine
            else 0
        )
        usage["slots"] = internal_slots + fixed_slots + side_engine_slots + fixed_engine_slots
        usage["engine_side_slots"] = side_engine_slots
        usage["fixed_engine_slots"] = fixed_engine_slots
        usage["internal_slots"] = internal_slots
        usage["fixed_slots"] = fixed_slots

        armor_points += usage["armor"] + usage["rear_armor"]

        # Player-installed equipment.
        for entry in build_comp.get("items") or ():
            item = data.item(entry.get("item_id"))
            if not item:
                usage["warnings"].append("Unknown item {0}".format(entry.get("item_id")))
                continue
            if not I.item_matches_faction(item, mech.get("faction")):
                usage["warnings"].append(
                    "{0} is not available to this tech base".format(I.item_display_name(item))
                )
            if I.is_engine(item) and name not in ENGINE_COMPONENTS:
                usage["warnings"].append("Engines mount in the centre torso only")
            if I.is_jump_jet(item) and name not in JUMP_JET_COMPONENTS:
                usage["warnings"].append("Jump jets cannot mount here")

            slots = B.effective_item_slots(data, item, build)
            usage["slots"] += slots
            artemis_bonus = (
                guidance_tons
                if I.is_artemis_weapon(item) and (build.get("upgrades") or {}).get("artemis")
                else 0.0
            )
            item_tonnage += I.item_tons(item) + artemis_bonus
            heat += W.weapon_heat(data, item) if I.is_weapon(item) else I.item_heat(item)
            mount = I.equipment_hardpoint_type(item)
            if mount:
                usage["hardpoints"][mount] = usage["hardpoints"].get(mount, 0) + 1
            if I.is_weapon(item) and not I.is_ams_weapon(item):
                alpha += W.weapon_total_damage(data, item, True, modules)
                weapon_items.append(item)
            if I.is_ammo(item):
                ammo_shots += W.effective_ammo_shots(item, quirks)
            if I.is_heat_sink(item):
                installed_heat_sinks += 1
            usage["items"].append(
                dict(
                    _describe_item(data, item),
                    slots=slots,
                    tons=_round(I.item_tons(item) + artemis_bonus),
                    weapon_group=entry.get("weapon_group"),
                )
            )

        # Hardpoint capacity vs. usage.
        for hardpoint in comp_def.get("hardpoints") or ():
            hp_type = I.hardpoint_type(hardpoint)
            if not hp_type:
                continue
            usage["hardpoint_capacity"][hp_type] = usage["hardpoint_capacity"].get(
                hp_type, 0
            ) + I.hardpoint_slots(hardpoint)
        for hp_type, used in usage["hardpoints"].items():
            capacity = usage["hardpoint_capacity"].get(hp_type, 0)
            if used > capacity:
                usage["warnings"].append(
                    "{0} hardpoints {1}/{2}".format(hp_type, used, capacity)
                )

        usage["preferred_structure_slots"] = int(
            finite_number(structure_by_component.get(name))
        )
        usage["preferred_armor_slots"] = int(finite_number(armor_by_component.get(name)))
        usage["fixed_armor_slots"] = int(finite_number(fixed_armor_by_component.get(name)))
        components[name] = usage

    _apply_durability(components, quirk_lookup)

    # -- engine heat sinks --------------------------------------------------
    for entry in build.get("engine_heat_sinks") or ():
        item = data.item(entry.get("item_id") if isinstance(entry, dict) else entry)
        if not item:
            continue
        item_tonnage += I.item_tons(item)
        heat += I.item_heat(item)
        installed_heat_sinks += 1


    # -- upgrade slot placement --------------------------------------------
    total_slot_capacity = sum(
        int(finite_number(((definition.get("components") or {}).get(name) or {}).get("slots")))
        for name in COMPONENT_ORDER
    )
    base_slot_usage = sum(usage["slots"] for usage in components.values())
    required_upgrade_slots = required_structure_slots + required_armor_slots
    reserved_usage = base_slot_usage + required_upgrade_slots
    upgrade_free_slots = max(0, total_slot_capacity - reserved_usage)

    for name, usage in components.items():
        slot_limit = usage["slot_limit"]
        available = max(0, slot_limit - usage["slots"])
        structure_slots = usage["preferred_structure_slots"]
        armor_slots = usage["preferred_armor_slots"]
        component_upgrade_slots = structure_slots + armor_slots
        fixed_armor_slots = usage["fixed_armor_slots"]
        floating = component_upgrade_slots - fixed_armor_slots
        occupied_floating = min(
            floating, max(0, available - fixed_armor_slots - upgrade_free_slots)
        )
        usage["occupied_upgrade_slots"] = fixed_armor_slots + occupied_floating
        usage["movable_upgrade_slots"] = component_upgrade_slots - usage["occupied_upgrade_slots"]
        usage["structure_slots"] = structure_slots
        usage["armor_slots"] = armor_slots
        usage["slots"] += usage["occupied_upgrade_slots"]
        if slot_limit and usage["slots"] > slot_limit:
            usage["warnings"].append("Slots {0}/{1}".format(usage["slots"], slot_limit))
        usage["free_slots"] = max(0, slot_limit - usage["slots"])

    if structure_unallocated:
        warnings.append(
            "{0} structure slot(s) could not be placed".format(structure_unallocated)
        )
    if armor_unallocated:
        warnings.append("{0} armor slot(s) could not be placed".format(armor_unallocated))

    used_slots = reserved_usage
    free_slots = max(0, total_slot_capacity - used_slots)

    # -- tonnage -------------------------------------------------------------
    structure_upgrade = data.item((build.get("upgrades") or {}).get("structure"))
    structure_tons = B.structure_upgrade_tonnage(max_tons, structure_upgrade)
    armor_tons = B.armor_tonnage(armor_points, armor_upgrade)
    used_tons = structure_tons + item_tonnage + armor_tons
    free_tons = max_tons - used_tons
    over_by = used_tons - max_tons
    is_overweight = bool(max_tons) and over_by > TONNAGE_EPSILON
    if is_overweight:
        # Show enough precision to explain a small overage that would otherwise
        # round to a tidy-looking "50.00 / 50.00".
        places = 2 if over_by >= 0.005 else 4
        warnings.append(
            "Overweight by {0:.{2}f}t ({1:.{2}f} / {3:.2f})".format(
                over_by, used_tons, places, max_tons
            )
        )

    # -- heat sinks and jump jets -------------------------------------------
    engine_included = I.engine_included_heat_sinks(engine)
    heat_sink_upgrade = data.item((build.get("upgrades") or {}).get("heatsinks"))
    is_double = "double" in str((heat_sink_upgrade or {}).get("display_name") or "").lower()
    total_heat_sinks = engine_included + installed_heat_sinks
    dissipation_per_sink = 0.2 if is_double else 0.1
    # The game data names these `heatdissipation_multiplier` and
    # `maxheat_multiplier`; `heatloss`/`heatcapacity` appear nowhere in it, so
    # the earlier names silently multiplied by 1.
    heat_dissipation = total_heat_sinks * dissipation_per_sink * quirk_multiplier(
        quirk_lookup, ["heatdissipation_multiplier"]
    )
    heat_capacity = (30.0 + total_heat_sinks * (2.0 if is_double else 1.0)) * quirk_multiplier(
        quirk_lookup, ["maxheat_multiplier"]
    )

    jump_jets = sum(
        1
        for usage in components.values()
        for item in usage["items"]
        if item.get("item_type") == "jumpjet"
    )
    jump_jet_slot_bonus = sum(
        max(0.0, finite_number(quirk.get("value")))
        for quirk in quirks
        if str(quirk.get("name") or "").lower() == "jumpjetslots_additive"
    )
    jump_jet_limit = max(0, int(finite_number(stats.get("MaxJumpJets")) + jump_jet_slot_bonus))
    if jump_jets > jump_jet_limit:
        warnings.append("Jump jets {0}/{1}".format(jump_jets, jump_jet_limit))

    # Front and rear armor share one pool per torso, so each cap counts once.
    max_armor_points = sum(usage["max_armor"] for usage in components.values())

    if engine:
        rating = I.engine_rating(engine)
        min_rating = int(finite_number(stats.get("MinEngineRating")))
        max_rating = int(finite_number(stats.get("MaxEngineRating")))
        if (min_rating and rating < min_rating) or (max_rating and rating > max_rating):
            warnings.append(
                "Engine {0} outside {1}-{2}".format(rating, min_rating, max_rating)
            )
    else:
        warnings.append("No engine installed")

    for name, usage in components.items():
        for warning in usage["warnings"]:
            warnings.append("{0}: {1}".format(usage["label"], warning))

    return {
        "mech": {
            "id": mech.get("id"),
            "name": mech.get("name"),
            "display_name": mech.get("display_name"),
            "chassis": mech.get("chassis"),
            "faction": mech.get("faction"),
            "weight_class": mech.get("weight_class"),
            "max_tons": max_tons,
            "is_omnimech": B.has_fixed_omnipods(data, mech),
        },
        "tonnage": {
            "max": _round(max_tons, 2),
            "used": _round(used_tons, 2),
            "free": _round(free_tons, 4),
            "equipment": _round(item_tonnage, 2),
            "structure": _round(structure_tons, 2),
            "armor": _round(armor_tons, 2),
            "over_by": _round(max(0.0, over_by), 4),
            "overweight": is_overweight,
        },
        "slots": {
            "total": total_slot_capacity,
            "used": used_slots,
            "free": free_slots,
            "structure_upgrade": required_structure_slots,
            "armor_upgrade": required_armor_slots,
        },
        "armor": {
            "points": armor_points,
            "max_points": max_armor_points,
            "tons": _round(armor_tons, 2),
            "per_ton": finite_number(
                (armor_upgrade or {}).get("stats", {}).get("armorPerTon"), 32.0
            ),
        },
        "heat": {
            "alpha_heat": _round(heat, 3),
            "heat_sinks": total_heat_sinks,
            "engine_heat_sinks": engine_included,
            "external_heat_sinks": installed_heat_sinks,
            "double": is_double,
            "dissipation": _round(heat_dissipation, 3),
            "capacity": _round(heat_capacity, 2),
        },
        "firepower": {
            "alpha_damage": _round(alpha, 3),
            "ammo_shots": _round(ammo_shots, 0),
        },
        "weapons": _weapon_metrics(
            data, weapon_items, quirks, modules, heat_dissipation, heat_capacity
        ),
        "movement": _movement(definition, engine, max_tons, quirk_lookup),
        "engine": _describe_engine(engine),
        "jump_jets": {"installed": jump_jets, "limit": jump_jet_limit},
        "components": components,
        "quirks": quirks,
        "warnings": warnings,
        "valid": not warnings,
    }


def _weapon_metrics(
    data: GameData,
    weapon_items: List[Dict[str, Any]],
    quirks: List[Dict[str, Any]],
    modules: List[Dict[str, Any]],
    dissipation: float,
    heat_capacity: float,
) -> Dict[str, Any]:
    """How fast the loadout puts out damage, and whether it can keep that up.

    `dps` is every weapon firing the moment it comes off cooldown, which is only
    sustainable while the heat sinks keep up. Heat efficiency is the share of the
    loadout's heat per second the mech can actually dissipate, so `sustained_dps`
    is `dps` scaled by it. Ported from `mechSummaryWeaponMetrics` in the
    reference client.

    Alpha heat here is the quirk-aware, weapons-only total — unlike
    `heat.alpha_heat`, which counts raw item heat across the whole build and is
    held to reference parity.
    """
    alpha_heat = 0.0
    dps = 0.0
    hps = 0.0

    for item in weapon_items:
        expected = WS.weapon_expected_cooldown(item, quirks, modules)
        cycle = max(
            WS.MINIMUM_CYCLE_SECONDS,
            expected if expected is not None else WS.weapon_timing(item, quirks, modules)["cycle"],
        )
        item_heat = WS.weapon_heat(data, item, quirks)
        alpha_heat += item_heat
        dps += W.weapon_total_damage(data, item, True, modules) / cycle
        # Machine guns, rotaries and beam lasers state their heat per second
        # already, so dividing by the cycle would count the cooldown twice.
        hps += item_heat if WS.is_continuous_per_second(item) else item_heat / cycle

    # A loadout that generates no more heat than it sheds runs flat out. The
    # epsilon keeps one that matches its cooling exactly from reading 99.9%.
    efficiency = (
        100.0
        if hps <= dissipation + 0.0001
        else max(0.0, min(100.0, dissipation / hps * 100))
    )

    return {
        "alpha_heat": _round(alpha_heat, 3),
        "alpha_heat_percent": (
            _round(alpha_heat / heat_capacity * 100, 1) if heat_capacity > 0 else 0.0
        ),
        "dps": _round(dps, 2),
        "sustained_dps": _round(dps * efficiency / 100, 2),
        "hps": _round(hps, 2),
        "heat_efficiency": _round(efficiency, 1),
    }


def _movement(
    definition: Dict[str, Any],
    engine: Optional[Dict[str, Any]],
    max_tons: float,
    quirk_lookup: Dict[str, float],
) -> Dict[str, Any]:
    """Top speed in kph, forward and reverse.

    Speed is the engine rating spread over the chassis' tonnage, scaled by the
    chassis' own `MaxMovementSpeed`. Reverse is that times the chassis'
    `ReverseSpeedMultiplier`. Quirks and pilot skills (Speed Tweak) arrive as
    `mechtopspeed_multiplier`, which applies to both directions, and
    `reversespeed_multiplier`, which applies to reverse only.
    """
    movement = definition.get("movement") or {}
    rating = I.engine_rating(engine) if engine else 0
    base_speed = (
        finite_number(movement.get("MaxMovementSpeed")) * rating / max_tons
        if max_tons and rating
        else 0.0
    )
    reverse_ratio = finite_number(movement.get("ReverseSpeedMultiplier"))
    top_speed_multiplier = quirk_multiplier(quirk_lookup, ["mechtopspeed_multiplier"])

    forward = base_speed * top_speed_multiplier
    reverse = (
        base_speed
        * reverse_ratio
        * top_speed_multiplier
        * quirk_multiplier(quirk_lookup, ["reversespeed_multiplier"])
    )

    return {
        "base_speed": _round(base_speed, 2),
        "speed": _round(forward, 2),
        "reverse_speed": _round(reverse, 2),
    }


# Component codes as they appear in durability quirk names, plus the rear
# variants used by the torsos.
_DURABILITY_CODES = {
    "head": ("hd", None),
    "left_arm": ("la", None),
    "left_torso": ("lt", "ltr"),
    "centre_torso": ("ct", "ctr"),
    "right_torso": ("rt", "rtr"),
    "right_arm": ("ra", None),
    "left_leg": ("ll", None),
    "right_leg": ("rl", None),
}


def _apply_durability(
    components: Dict[str, Dict[str, Any]], quirk_lookup: Dict[str, float]
) -> None:
    """Effective armor and structure after quirks and durability skills.

    Additive quirks raise the value directly; the skill multipliers scale the
    total and floor it. Neither changes how many points may be allocated - a
    component's capacity is fixed by its internals.
    """
    armor_skill = finite_number(quirk_lookup.get("increasedarmor_multiplier"))
    structure_skill = finite_number(quirk_lookup.get("increasedstructure_multiplier"))

    for name, usage in components.items():
        code, rear_code = _DURABILITY_CODES.get(name, (None, None))
        if not code:
            continue

        front_bonus = quirk_add(quirk_lookup, "armorresist", code)
        rear_bonus = (
            finite_number(quirk_lookup.get("armorresist_all_additive"))
            + finite_number(quirk_lookup.get("armorresist_{0}_additive".format(rear_code)))
            if rear_code
            else 0.0
        )
        structure_bonus = quirk_add(quirk_lookup, "internalresist", code)

        front = max(0.0, usage["armor"] + front_bonus)
        rear = max(0.0, usage["rear_armor"] + rear_bonus)
        total_before = front + rear
        total_after = durability_skill_final_value(total_before, armor_skill)

        structure_before = usage["structure"] + structure_bonus
        structure_after = durability_skill_final_value(structure_before, structure_skill)

        usage["effective_armor"] = int(front + (total_after - total_before)) if rear_code else int(total_after)
        usage["effective_rear_armor"] = int(rear) if rear_code else 0
        usage["effective_structure"] = int(structure_after)


def _component_quirks(
    quirks: List[Dict[str, Any]], component: str
) -> List[Dict[str, Any]]:
    """Quirks that apply to one component, e.g. `armor_rt_additive` on the right torso."""
    code = COMPONENT_QUIRK_CODES.get(component)
    if not code:
        return []
    return [quirk for quirk in quirks if quirk_family(quirk.get("name")) == code]


def _installed_modules(
    data: GameData, definition: Dict[str, Any], build: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """Every `module` item mounted on the mech, fixed or installed.

    Only these can rewrite weapon stats, so they are collected once per
    calculation and threaded through the damage helpers.
    """
    modules: List[Dict[str, Any]] = []
    for name in COMPONENT_ORDER:
        comp_def = (definition.get("components") or {}).get(name) or {}
        build_comp = (build.get("components") or {}).get(name) or {}
        item_ids = list(comp_def.get("fixed") or []) + [
            entry.get("item_id") for entry in build_comp.get("items") or ()
        ]
        for item_id in item_ids:
            item = data.item(item_id)
            if item and item.get("item_type") == "module":
                modules.append(item)
    return modules


def item_category(item: Dict[str, Any]) -> str:
    """Coarse class used to colour an item in the slot grid.

    Domain knowledge, so it lives here rather than being re-derived from item
    names in the stylesheet.
    """
    if I.is_engine(item):
        return "engine"
    if I.is_heat_sink(item):
        return "heatsink"
    if I.is_ammo(item):
        return "ammo-{0}".format(I.ammo_class(item) or "other")
    if I.is_jump_jet(item):
        return "jumpjet"
    if I.is_weapon(item):
        return "weapon-{0}".format(I.equipment_hardpoint_type(item) or "other")
    if I.is_ecm(item):
        return "ecm"
    if item.get("item_type") == "internal":
        return "internal"
    if item.get("item_type") == "masc":
        return "masc"
    return "equipment"


SENSOR_CTYPES = ("CTargetingComputerStats", "CBAPStats", "CClanBAPStats", "CClanLightBAPStats")


def catalogue_group(item: Dict[str, Any]) -> str:
    """Shelf an item sits on in the equipment catalogue.

    Weapons and ammo shelve by weapon class; equipment splits into ECM, sensor
    (probes and targeting computers) and misc, the way MechDB's warehouse
    lays them out. Everything else is one shelf per item type.
    """
    if I.is_weapon(item):
        return I.equipment_hardpoint_type(item) or "other"
    if I.is_ammo(item):
        return I.ammo_class(item) or "other"
    if I.is_ecm(item):
        return "ecm"
    if item.get("ctype") in SENSOR_CTYPES:
        return "sensor"
    item_type = str(item.get("item_type") or "")
    if item_type == "module":
        return "misc"
    return item_type or "other"


def _describe_item(data: GameData, item: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "category": item_category(item),
        "id": item.get("id"),
        "name": item.get("name"),
        "display_name": I.item_display_name(item),
        "item_type": item.get("item_type"),
        "family": item.get("family"),
        "slots": I.item_slots(item),
        "tons": _round(I.item_tons(item)),
        "heat": _round(W.weapon_heat(data, item) if I.is_weapon(item) else I.item_heat(item)),
        "hardpoint_type": I.equipment_hardpoint_type(item),
        "damage": _round(W.weapon_total_damage(data, item)) if I.is_weapon(item) else None,
    }


def _describe_engine(engine: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not engine:
        return None
    return {
        "id": engine.get("id"),
        "display_name": I.item_display_name(engine),
        "rating": I.engine_rating(engine),
        "tons": _round(I.item_tons(engine)),
        "slots": I.item_slots(engine),
        "side_slots": I.engine_side_slots(engine),
        "included_heat_sinks": I.engine_included_heat_sinks(engine),
        "heat_sink_capacity": I.engine_additional_heat_sink_capacity(engine),
    }
