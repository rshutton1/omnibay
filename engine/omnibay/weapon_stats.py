"""Per-weapon statistics with quirks and equipment applied.

Backs the hover tooltip: base values, the values a mech's quirks actually
produce, and a trail of which effects did what. Ported from the tooltip and
simulation helpers in the reference client's `public/app.js`.

The rule throughout is that a quirk applies to a weapon if its name matches
either a broad category (`all_`, `ballistic_`, `energy_`, `missile_`) or the
weapon itself (`isautocannon20_cooldown_multiplier`). Direction matters: some
families are reductions, some increases, some signed.
"""
import math
from typing import Any, Dict, FrozenSet, List, Optional, Sequence, Tuple

from omnibay import items as I
from omnibay.quirks import finite_number
from omnibay.weapons import (
    effective_weapon_stats,
    is_rocket_launcher,
    normalize_lookup_key,
    simulation_item_keys,
    weapon_direct_damage,
    weapon_total_damage,
)

Item = Dict[str, Any]
Quirk = Dict[str, Any]

# Quirks that name a broad category directly. They are handled by the explicit
# category checks, so the "specific weapon" pass must not count them twice.
DIRECT_QUIRKS: Dict[str, FrozenSet[str]] = {
    "_cooldown_multiplier": frozenset(
        {
            "all_cooldown_multiplier",
            "energy_cooldown_multiplier",
            "missile_cooldown_multiplier",
            "ballistic_cooldown_multiplier",
        }
    ),
    "_heat_multiplier": frozenset(
        {
            "all_heat_multiplier",
            "energy_heat_multiplier",
            "missile_heat_multiplier",
            "ballistic_heat_multiplier",
        }
    ),
    "_duration_multiplier": frozenset(
        {"all_duration_multiplier", "energy_duration_multiplier"}
    ),
    "_range_multiplier": frozenset(
        {
            "all_range_multiplier",
            "energy_range_multiplier",
            "missile_range_multiplier",
            "ballistic_range_multiplier",
        }
    ),
    "_velocity_multiplier": frozenset(
        {
            "all_velocity_multiplier",
            "energy_velocity_multiplier",
            "missile_velocity_multiplier",
            "ballistic_velocity_multiplier",
        }
    ),
    "_spread_multiplier": frozenset(
        {"all_spread_multiplier", "missile_spread_multiplier", "ballistic_spread_multiplier"}
    ),
}

# Suffixes where naming the weapon's own category is already covered above.
_CATEGORY_AWARE_SUFFIXES = frozenset(
    {
        "_cooldown_multiplier",
        "_heat_multiplier",
        "_range_multiplier",
        "_velocity_multiplier",
        "_spread_multiplier",
    }
)

MINIMUM_CYCLE_SECONDS = 0.016


# --------------------------------------------------------------------------
# Weapon classification
# --------------------------------------------------------------------------


def is_ultra_autocannon(item: Optional[Item]) -> bool:
    return any("ultraautocannon" in key for key in simulation_item_keys(item))


def is_streak_srm(item: Optional[Item]) -> bool:
    return "streaksrm" in simulation_item_keys(item)


def is_hitscan(item: Optional[Item]) -> bool:
    """No projectile class means the shot lands instantly, so velocity is moot."""
    if (item or {}).get("item_type") != "weapon":
        return False
    return not str((item or {}).get("stats", {}).get("projectileclass") or "").strip()


def is_continuous_beam(item: Optional[Item]) -> bool:
    """Beam lasers and flamers deal damage per second rather than per shot."""
    return any(
        "beamlaser" in key or "flamer" in key for key in simulation_item_keys(item)
    )


def is_continuous_per_second(item: Optional[Item]) -> bool:
    keys = simulation_item_keys(item)
    return bool(
        keys
        & {
            "machinegun",
            "ismachinegun",
            "clanmachinegun",
            "rotaryautocannon",
            "clanbeamlaser",
            "flamer",
        }
    )


def ghost_heat_group_key(item: Optional[Item]) -> str:
    shared = int(finite_number((item or {}).get("stats", {}).get("heatPenaltyID")))
    if shared > 0:
        return "shared:{0}".format(shared)
    key = normalize_lookup_key((item or {}).get("name"))
    if key.endswith("artemis"):
        key = key[: -len("artemis")]
    return "singleton:{0}".format(key) if key else ""


# --------------------------------------------------------------------------
# Quirk matching
# --------------------------------------------------------------------------


def directional_quirk_value(quirk: Quirk, direction: str = "reduction") -> float:
    """Read a quirk in the direction its family uses.

    `reduction` keeps only negatives (as a positive magnitude), `increase` keeps
    only positives, `signed` keeps the value as-is.
    """
    value = finite_number(quirk.get("value"))
    if direction == "signed":
        return value
    if direction == "reduction":
        return max(0.0, -value)
    return max(0.0, value)


def specific_quirk_matches_item(prefix: str, item: Optional[Item]) -> bool:
    keys = simulation_item_keys(item)
    if prefix in keys:
        return True
    # AMS quirks name the full system, e.g. `clanantimissilesystem`.
    return I.is_ams_weapon(item) and prefix.endswith("antimissilesystem") and any(
        key.endswith(prefix) for key in keys
    )


def specific_quirk_value(
    quirk: Quirk, item: Optional[Item], suffix: str, direction: str = "reduction"
) -> float:
    """Value of a quirk that names this specific weapon, or 0."""
    name = str(quirk.get("name") or "").lower()
    if not name.endswith(suffix):
        return 0.0
    if name in DIRECT_QUIRKS.get(suffix, frozenset()):
        return 0.0
    if suffix in _CATEGORY_AWARE_SUFFIXES and name == "{0}{1}".format(
        I.equipment_hardpoint_type(item), suffix
    ):
        return 0.0
    prefix = normalize_lookup_key(name[: -len(suffix)])
    if not prefix or not specific_quirk_matches_item(prefix, item):
        return 0.0
    return directional_quirk_value(quirk, direction)


def _merge_quirks(quirks: Sequence[Quirk]) -> List[Quirk]:
    """Collapse duplicate quirk names, summing their values."""
    merged: Dict[str, Quirk] = {}
    for quirk in quirks or ():
        name = str(quirk.get("name") or "").lower()
        if not name:
            continue
        entry = merged.get(name)
        if entry is None:
            entry = {
                "name": name,
                "display_name": quirk.get("display_name") or name,
                "value": 0.0,
                "sources": [],
            }
            merged[name] = entry
        entry["value"] += finite_number(quirk.get("value"))
        for source in quirk.get("sources") or ():
            if source not in entry["sources"]:
                entry["sources"].append(source)
    return list(merged.values())


# --------------------------------------------------------------------------
# Effect collection
# --------------------------------------------------------------------------


def collect_weapon_quirk_effects(
    item: Optional[Item], quirks: Optional[Sequence[Quirk]] = None
) -> Dict[str, Any]:
    """Totals per effect family, plus which quirks contributed to each."""
    totals = {
        "cooldown_reduction": 0.0,
        "duration_modifier": 0.0,
        "rof_bonus": 0.0,
        "heat_reduction": 0.0,
        "range_bonus": 0.0,
        "velocity_bonus": 0.0,
        "spread_modifier": 0.0,
        "damage_additive": 0.0,
        "jam_chance_reduction": 0.0,
        "jam_duration_reduction": 0.0,
        "hsl_bonus": 0.0,
    }
    applied: Dict[str, Dict[str, Any]] = {}

    stats = (item or {}).get("stats") or {}
    hardpoint = I.equipment_hardpoint_type(item)
    continuous = is_continuous_beam(item)
    uses_rof = finite_number(stats.get("rof")) > 0
    standard_timing = not continuous and not uses_rof
    has_range = any(finite_number(r.get("start")) > 0 for r in (item or {}).get("ranges") or ())
    has_velocity = finite_number(stats.get("speed")) > 0 and not is_hitscan(item)
    has_spread = finite_number(stats.get("spread")) > 0
    ultra = is_ultra_autocannon(item)
    has_ghost_heat = bool(ghost_heat_group_key(item))

    def record(quirk: Quirk, effect: str, value: float, harmful: bool = False) -> None:
        if abs(value) < 0.0001:
            return
        name = str(quirk.get("name") or "").lower()
        if not name:
            return
        entry = applied.setdefault(
            name,
            {
                "name": name,
                "display_name": quirk.get("display_name") or name,
                "effects": [],
                # Magnitude of the effect, in the direction its family uses.
                "value": 0.0,
                # The quirk's own signed value, so the card reads the same way
                # the quirk list does (a -15% cooldown quirk shows as -15%).
                "quirk_value": finite_number(quirk.get("value")),
                "harmful": False,
                "sources": list(quirk.get("sources") or ()),
            },
        )
        if effect not in entry["effects"]:
            entry["effects"].append(effect)
        entry["value"] += value
        entry["harmful"] = entry["harmful"] or harmful

    for quirk in _merge_quirks(quirks or ()):
        name = str(quirk.get("name") or "").lower()
        if not name:
            continue

        if standard_timing and not is_rocket_launcher(item) and finite_number(stats.get("cooldown")) > 0:
            value = 0.0
            if name in ("all_cooldown_multiplier", "{0}_cooldown_multiplier".format(hardpoint)):
                value += directional_quirk_value(quirk, "reduction")
            value += specific_quirk_value(quirk, item, "_cooldown_multiplier", "reduction")
            totals["cooldown_reduction"] += value
            record(quirk, "cooldown", value)

        if standard_timing and finite_number(stats.get("duration")) > 0:
            value = 0.0
            if name == "all_duration_multiplier" or (
                hardpoint == "energy" and name == "energy_duration_multiplier"
            ):
                value += directional_quirk_value(quirk, "signed")
            value += specific_quirk_value(quirk, item, "_duration_multiplier", "signed")
            totals["duration_modifier"] += value
            record(quirk, "duration", value, value > 0)

        if uses_rof:
            value = specific_quirk_value(quirk, item, "_rof_multiplier", "increase")
            totals["rof_bonus"] += value
            record(quirk, "rof", value)

        heat_value = 0.0
        if name in ("all_heat_multiplier", "{0}_heat_multiplier".format(hardpoint)):
            heat_value += directional_quirk_value(quirk, "reduction")
        heat_value += specific_quirk_value(quirk, item, "_heat_multiplier", "reduction")
        totals["heat_reduction"] += heat_value
        if I.item_heat(item) > 0:
            record(quirk, "heat", heat_value)

        range_value = 0.0
        if name in ("all_range_multiplier", "{0}_range_multiplier".format(hardpoint)):
            range_value += directional_quirk_value(quirk, "increase")
        range_value += specific_quirk_value(quirk, item, "_range_multiplier", "increase")
        totals["range_bonus"] += range_value
        if has_range:
            record(quirk, "range", range_value)

        velocity_value = 0.0
        if name in ("all_velocity_multiplier", "{0}_velocity_multiplier".format(hardpoint)):
            velocity_value += directional_quirk_value(quirk, "increase")
        velocity_value += specific_quirk_value(quirk, item, "_velocity_multiplier", "increase")
        totals["velocity_bonus"] += velocity_value
        if has_velocity:
            record(quirk, "velocity", velocity_value)

        spread_value = 0.0
        if name in ("all_spread_multiplier", "{0}_spread_multiplier".format(hardpoint)):
            spread_value += directional_quirk_value(quirk, "signed")
        spread_value += specific_quirk_value(quirk, item, "_spread_multiplier", "signed")
        totals["spread_modifier"] += spread_value
        if has_spread:
            record(quirk, "spread", spread_value, spread_value > 0)

        if I.is_ams_weapon(item):
            value = specific_quirk_value(quirk, item, "_damage_additive", "increase")
            totals["damage_additive"] += value
            record(quirk, "damage", value)

        if ultra and finite_number(stats.get("JammingChance")) > 0:
            value = (
                directional_quirk_value(quirk, "reduction")
                if name == "all_jamchance_multiplier"
                else 0.0
            )
            value += specific_quirk_value(quirk, item, "_jamchance_multiplier", "reduction")
            totals["jam_chance_reduction"] += value
            record(quirk, "jam chance", value)

        if ultra and finite_number(stats.get("JammedTime")) > 0:
            value = (
                directional_quirk_value(quirk, "reduction")
                if name == "all_jamduration_multiplier"
                else 0.0
            )
            value += specific_quirk_value(quirk, item, "_jamduration_multiplier", "reduction")
            totals["jam_duration_reduction"] += value
            record(quirk, "jam duration", value)

        if name.endswith("_minheatpenaltylevel_additive"):
            suffix = "_minheatpenaltylevel_additive"
            prefix = normalize_lookup_key(name[: -len(suffix)])
            matches = (
                prefix in ("all", "weapon", "weapons")
                or prefix == normalize_lookup_key(hardpoint)
                or specific_quirk_matches_item(prefix, item)
            )
            value = max(0.0, finite_number(quirk.get("value"))) if matches else 0.0
            totals["hsl_bonus"] += value
            if has_ghost_heat:
                record(quirk, "heat scale", value)

    return {"totals": totals, "applied": sorted(applied.values(), key=lambda e: e["display_name"])}


# --------------------------------------------------------------------------
# Derived firing behaviour
# --------------------------------------------------------------------------


def weapon_volley_size(item: Optional[Item]) -> int:
    if I.equipment_hardpoint_type(item) != "missile":
        return 1
    stats = (item or {}).get("stats") or {}
    if is_streak_srm(item):
        return max(1, int(finite_number(stats.get("numFiring"), 1)))
    return max(1, int(finite_number(stats.get("volleysize"), 1)))


def weapon_firing_profile(
    item: Optional[Item], modules: Optional[Sequence[Item]] = None
) -> Dict[str, Any]:
    """How a trigger pull is broken into shots, and how they are spaced."""
    effective = effective_weapon_stats(item, modules)
    shots = max(1, int(effective["numFiring"]))
    per_shot = max(1, int(effective["numPerShot"]))
    volley = weapon_volley_size(item)

    full_events = shots // volley
    remainder = shots % volley
    event_count = full_events + (1 if remainder else 0)
    shot_delay = max(0.0, effective["volleydelay"]) if shots > 1 else 0.0
    total_projectiles = shots * per_shot
    simultaneous = event_count <= 1 or shot_delay <= 0

    if simultaneous:
        display = str(total_projectiles)
    else:
        display = "{0} X {1}".format(volley * per_shot, full_events)
        if remainder * per_shot > 0:
            display += " + {0}".format(remainder * per_shot)

    return {
        "shots": shots,
        "shot_delay": shot_delay,
        "event_count": event_count,
        "total_projectiles": total_projectiles,
        "simultaneous": simultaneous,
        "display_shots": display,
    }


def weapon_firing_time(item: Optional[Item], modules: Optional[Sequence[Item]] = None) -> float:
    profile = weapon_firing_profile(item, modules)
    return max(0, profile["event_count"] - 1) * profile["shot_delay"]


def weapon_timing(
    item: Optional[Item],
    quirks: Optional[Sequence[Quirk]] = None,
    modules: Optional[Sequence[Item]] = None,
) -> Dict[str, float]:
    stats = (item or {}).get("stats") or {}
    if is_continuous_beam(item):
        return {"duration": 0.0, "cooldown": 0.0, "cycle": 1.0}

    rof = finite_number(stats.get("rof"))
    if rof > 0:
        bonus = collect_weapon_quirk_effects(item, quirks)["totals"]["rof_bonus"]
        cycle = max(MINIMUM_CYCLE_SECONDS, 1 / (rof * (1 + bonus)))
        return {"duration": 0.0, "cooldown": cycle, "cycle": cycle}

    totals = collect_weapon_quirk_effects(item, quirks)["totals"]
    cooldown = max(
        0.0,
        effective_weapon_stats(item, modules)["cooldown"]
        * max(0.0, 1 - totals["cooldown_reduction"]),
    )
    duration = max(0.0, finite_number(stats.get("duration")) * max(0.0, 1 + totals["duration_modifier"]))
    return {
        "duration": duration,
        "cooldown": cooldown,
        "cycle": max(MINIMUM_CYCLE_SECONDS, cooldown + duration),
    }


def weapon_heat(data, item: Optional[Item], quirks: Optional[Sequence[Quirk]] = None) -> float:
    from omnibay.weapons import weapon_heat as base_weapon_heat

    reduction = collect_weapon_quirk_effects(item, quirks)["totals"]["heat_reduction"]
    return max(0.0, base_weapon_heat(data, item) * max(0.0, 1 - reduction))


def ultra_autocannon_jam_stats(
    item: Optional[Item], quirks: Optional[Sequence[Quirk]] = None
) -> Dict[str, float]:
    stats = (item or {}).get("stats") or {}
    base_chance = max(0.0, finite_number(stats.get("JammingChance")))
    base_duration = max(0.0, finite_number(stats.get("JammedTime")))
    totals = collect_weapon_quirk_effects(item, quirks)["totals"]
    return {
        "base_chance": base_chance,
        "chance": max(0.0, min(1.0, base_chance * max(0.0, 1 - totals["jam_chance_reduction"]))),
        "base_duration": base_duration,
        "duration": max(0.0, base_duration * max(0.0, 1 - totals["jam_duration_reduction"])),
    }


def weapon_has_expected_cooldown(
    item: Optional[Item], modules: Optional[Sequence[Item]] = None
) -> bool:
    stats = (item or {}).get("stats") or {}
    return (
        is_ultra_autocannon(item)
        or finite_number(stats.get("chargeTime")) > 0
        or finite_number(stats.get("duration")) > 0
        or weapon_firing_time(item, modules) > 0
    )


def weapon_expected_cooldown(
    item: Optional[Item],
    quirks: Optional[Sequence[Quirk]] = None,
    modules: Optional[Sequence[Item]] = None,
) -> Optional[float]:
    """Real time between trigger pulls, including burn time and jam risk."""
    if not weapon_has_expected_cooldown(item, modules):
        return None
    stats = (item or {}).get("stats") or {}
    timing = weapon_timing(item, quirks, modules)
    firing_time = weapon_firing_time(item, modules)

    if is_ultra_autocannon(item):
        jam = ultra_autocannon_jam_stats(item, quirks)
        return (
            firing_time
            + (1 - jam["chance"]) * timing["cooldown"]
            + jam["chance"] * max(timing["cooldown"], jam["duration"])
        ) / max(1.0, 2 - jam["chance"])

    return max(
        MINIMUM_CYCLE_SECONDS,
        max(0.0, finite_number(stats.get("chargeTime")))
        + firing_time
        + timing["duration"]
        + timing["cooldown"],
    )


def weapon_range_profile(item: Optional[Item], range_bonus: float = 0.0) -> Optional[Dict[str, float]]:
    """Effective ranges after quirks. The minimum range is never scaled."""
    multiplier = max(0.0, 1 + finite_number(range_bonus))
    source = sorted(
        (
            {
                "start": finite_number(r.get("start")),
                "modifier": max(0.0, finite_number(r.get("damageModifier"))),
            }
            for r in (item or {}).get("ranges") or ()
        ),
        key=lambda r: r["start"],
    )
    if not source:
        return None

    max_modifier = max(r["modifier"] for r in source)
    full = [r for r in source if abs(r["modifier"] - max_modifier) < 0.0001]
    minimum = full[0]["start"] if full else source[0]["start"]
    optimal = full[-1]["start"] if full else source[0]["start"]
    scaled = [r["start"] if r["start"] <= minimum else r["start"] * multiplier for r in source]

    has_minimum = minimum > source[0]["start"] and source[0]["modifier"] < max_modifier
    return {
        "minimum_range": minimum if has_minimum else 0.0,
        "optimal_range": optimal if optimal <= minimum else optimal * multiplier,
        "maximum_range": scaled[-1],
        "multiplier": multiplier,
    }


# --------------------------------------------------------------------------
# Tooltip payload
# --------------------------------------------------------------------------


def _pair(base: float, final: float, places: int = 2) -> Dict[str, Any]:
    """A stat as base and quirked value, flagged when the two differ."""
    return {
        "base": round(base, places),
        "final": round(final, places),
        "changed": abs(base - final) > 10 ** -(places + 1),
    }


def critical_chances(item: Optional[Item]) -> List[float]:
    raw = str((item or {}).get("stats", {}).get("critChanceIncrease") or "")
    values = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            values.append(float(part))
        except ValueError:
            continue
    return values if any(v for v in values) else []


def weapon_tooltip(
    data,
    item: Optional[Item],
    quirks: Optional[Sequence[Quirk]] = None,
    modules: Optional[Sequence[Item]] = None,
) -> Optional[Dict[str, Any]]:
    """Everything the hover card shows for one weapon."""
    if not I.is_weapon(item):
        return None

    stats = (item or {}).get("stats") or {}
    quirks = list(quirks or ())
    modules = list(modules or ())
    effects = collect_weapon_quirk_effects(item, quirks)
    totals = effects["totals"]

    base_damage = max(0.0, weapon_total_damage(data, item, True, []))
    final_damage = max(0.0, weapon_total_damage(data, item, True, modules))

    from omnibay.weapons import weapon_heat as base_weapon_heat

    base_heat = max(0.0, base_weapon_heat(data, item))
    final_heat = weapon_heat(data, item, quirks)

    base_timing = weapon_timing(item, [], [])
    final_timing = weapon_timing(item, quirks, modules)
    base_expected = weapon_expected_cooldown(item, [], [])
    final_expected = weapon_expected_cooldown(item, quirks, modules)
    base_cycle = base_expected if base_expected is not None else base_timing["cycle"]
    final_cycle = final_expected if final_expected is not None else final_timing["cycle"]

    base_ranges = weapon_range_profile(item, 0.0)
    final_ranges = weapon_range_profile(item, totals["range_bonus"])

    base_velocity = max(0.0, finite_number(stats.get("speed")))
    final_velocity = base_velocity * (1 + totals["velocity_bonus"])

    profile = weapon_firing_profile(item, modules)
    continuous = is_continuous_per_second(item)

    # Damage and heat per second, using the real cycle time.
    rate_rows: Dict[str, Dict[str, Any]] = {}
    if base_cycle > 0 and final_cycle > 0 and final_damage > 0:
        rate_rows["dps"] = _pair(base_damage / base_cycle, final_damage / final_cycle)
    if base_heat > 0 and final_heat > 0 and final_damage > 0:
        rate_rows["dph"] = _pair(base_damage / base_heat, final_damage / final_heat)
    if base_heat > 0 and base_cycle > 0 and final_cycle > 0:
        rate_rows["hps"] = _pair(base_heat / base_cycle, final_heat / final_cycle)

    payload: Dict[str, Any] = {
        "id": item.get("id"),
        "name": I.item_display_name(item),
        "category": "weapon-{0}".format(I.equipment_hardpoint_type(item) or "other"),
        "hardpoint_type": I.equipment_hardpoint_type(item),
        "tons": I.item_tons(item),
        "slots": I.item_slots(item),
        "damage": _pair(base_damage, final_damage),
        "heat": _pair(base_heat, final_heat),
        "cooldown": _pair(base_timing["cooldown"], final_timing["cooldown"]),
        "rates": rate_rows,
        "shots": profile["display_shots"],
        "shot_interval": round(profile["shot_delay"], 3) if profile["shot_delay"] > 0 else None,
        "continuous": continuous,
        "applied_effects": [
            {
                "name": entry["display_name"],
                "effects": entry["effects"],
                "value": round(entry["value"], 4),
                "quirk_value": round(entry["quirk_value"], 4),
                "harmful": entry["harmful"],
                "sources": entry["sources"],
            }
            for entry in effects["applied"]
        ],
    }

    if base_expected is not None and final_expected is not None:
        payload["expected_cooldown"] = _pair(base_expected, final_expected)
    if finite_number(stats.get("duration")) > 0:
        payload["duration"] = _pair(base_timing["duration"], final_timing["duration"])
    if base_ranges and final_ranges:
        payload["optimal_range"] = _pair(
            base_ranges["optimal_range"], final_ranges["optimal_range"], 0
        )
        payload["max_range"] = _pair(base_ranges["maximum_range"], final_ranges["maximum_range"], 0)
        if final_ranges["minimum_range"] > 0:
            payload["min_range"] = _pair(
                base_ranges["minimum_range"], final_ranges["minimum_range"], 0
            )
    if base_velocity > 0 and not is_hitscan(item):
        payload["velocity"] = _pair(base_velocity, final_velocity, 0)
    if finite_number(stats.get("spread")) > 0:
        spread = max(0.0, finite_number(stats.get("spread")))
        payload["spread"] = _pair(spread, spread * (1 + totals["spread_modifier"]), 2)
    if is_ultra_autocannon(item):
        jam = ultra_autocannon_jam_stats(item, quirks)
        payload["jam_chance"] = _pair(jam["base_chance"], jam["chance"], 4)
        payload["jam_duration"] = _pair(jam["base_duration"], jam["duration"], 2)

    chances = critical_chances(item)
    if chances:
        payload["critical_chance"] = chances

    return payload
