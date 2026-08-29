"""Weapon damage and ammunition.

Ported from the weapon helpers in the reference `public/app.js`. Two module
systems modify weapon stats and both are narrow:

* Railgun capacitors apply unconditionally to Railguns (`always_applied_...`).
* Modules 9031 and 9032 — the modified ballistic and missile loaders — rewrite
  a whitelisted set of fields for the weapons they list, but only while the
  module is actually installed.
"""
import math
import re
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set

from omnibay.items import _stats, is_weapon, item_tons
from omnibay.quirks import finite_number

# Only these two modules may rewrite weapon stats, and only these fields.
SUPPORTED_WEAPON_MODIFIER_FIELDS: Dict[int, Set[str]] = {
    9031: {"damage", "numFiring", "numPerShot", "spread", "volleydelay"},
    9032: {"numFiring", "ammoPerShot", "volleydelay", "cooldown", "minReactivationTime"},
}

_NON_ALNUM = re.compile(r"[^a-z0-9]")


def normalize_lookup_key(value: Any) -> str:
    return _NON_ALNUM.sub("", str(value or "").lower())


def simulation_item_keys(item: Optional[Dict[str, Any]]) -> Set[str]:
    """Every name an item may be referenced by, normalized."""
    item = item or {}
    candidates = [item.get("name"), item.get("display_name")]
    candidates.extend(str(item.get("aliases") or "").split(","))
    return {key for key in (normalize_lookup_key(c) for c in candidates) if key}


def is_rocket_launcher(item: Optional[Dict[str, Any]]) -> bool:
    return "rocketlauncher" in simulation_item_keys(item)


# --------------------------------------------------------------------------
# Module bonuses
# --------------------------------------------------------------------------


def always_applied_weapon_module_bonus(data, item: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """The bonus a two-slot capacitor grants whenever its weapon is mounted."""
    if not is_weapon(item):
        return {"damage": 0.0, "heat": 0.0, "source": None}

    cache = getattr(data, "_always_applied_bonus_cache", None)
    if cache is None:
        cache = {}
        setattr(data, "_always_applied_bonus_cache", cache)
    cache_key = str(item.get("id") if item.get("id") is not None else item.get("name"))
    if cache_key in cache:
        return cache[cache_key]

    weapon_key = normalize_lookup_key(item.get("name"))
    matching = []
    for module in data.items.values():
        if module.get("item_type") != "module":
            continue
        if finite_number((module.get("stats") or {}).get("amountAllowed")) != 2:
            continue
        for filt in module.get("weapon_stat_filters") or ():
            names = [normalize_lookup_key(n) for n in filt.get("compatible_weapons") or ()]
            if weapon_key not in names:
                continue
            if any(
                str(entry.get("operation") or "") == "+"
                and (finite_number(entry.get("damage")) != 0 or finite_number(entry.get("heat")) != 0)
                for entry in filt.get("weapon_stats") or ()
            ):
                matching.append(module)
                break

    from omnibay.loader import normalize_faction

    module = None
    for candidate in matching:
        if normalize_faction(candidate.get("faction")) == normalize_faction(item.get("faction")):
            module = candidate
            break
    if module is None and matching:
        module = matching[0]

    count = max(0, int(finite_number((module or {}).get("stats", {}).get("amountAllowed"))))
    bonus: Dict[str, Any] = {
        "damage": 0.0,
        "heat": 0.0,
        "source": None
        if not module
        else {
            "id": module.get("id"),
            "name": module.get("name"),
            "display_name": module.get("display_name") or module.get("name"),
            "count": count,
        },
    }
    for filt in (module or {}).get("weapon_stat_filters") or ():
        names = [normalize_lookup_key(n) for n in filt.get("compatible_weapons") or ()]
        if weapon_key not in names:
            continue
        for entry in filt.get("weapon_stats") or ():
            if str(entry.get("operation") or "") != "+":
                continue
            bonus["damage"] += finite_number(entry.get("damage")) * count
            bonus["heat"] += finite_number(entry.get("heat")) * count

    cache[cache_key] = bonus
    return bonus


def _modifier_field_value(source: Dict[str, Any], field: str) -> float:
    if field == "minReactivationTime":
        for key in ("MinReactivationTime", "MinReactivationTIme", "minReactivationTime"):
            if key in source:
                return finite_number(source.get(key))
        return 0.0
    return finite_number(source.get(field), 1.0 if field == "numFiring" else 0.0)


def _modifier_operand(entry: Dict[str, Any], field: str) -> Optional[float]:
    if field == "minReactivationTime":
        for key in ("MinReactivationTime", "MinReactivationTIme", "minReactivationTime"):
            if key in entry:
                return finite_number(entry.get(key), float("nan"))
        return None
    if field not in entry:
        return None
    value = finite_number(entry.get(field), float("nan"))
    return None if value != value else value


def effective_weapon_stats(
    item: Optional[Dict[str, Any]], modules: Optional[Sequence[Dict[str, Any]]] = None
) -> Dict[str, float]:
    """Base weapon stats with any installed loader-module modifiers applied."""
    source = _stats(item)
    values = {
        field: _modifier_field_value(source, field)
        for field in (
            "damage",
            "numFiring",
            "numPerShot",
            "spread",
            "volleydelay",
            "cooldown",
            "ammoPerShot",
            "minReactivationTime",
        )
    }

    weapon_key = normalize_lookup_key((item or {}).get("name"))
    for module in modules or ():
        supported = SUPPORTED_WEAPON_MODIFIER_FIELDS.get(
            int(finite_number((module or {}).get("id")))
        )
        if not supported:
            continue
        for filt in module.get("weapon_stat_filters") or ():
            names = [normalize_lookup_key(n) for n in filt.get("compatible_weapons") or ()]
            if not weapon_key or weapon_key not in names:
                continue
            for entry in filt.get("weapon_stats") or ():
                operation = str(entry.get("operation") or "")
                if operation not in ("+", "*"):
                    continue
                for field in supported:
                    operand = _modifier_operand(entry, field)
                    if operand is None:
                        continue
                    values[field] = (
                        values[field] + operand if operation == "+" else values[field] * operand
                    )
    return values


# --------------------------------------------------------------------------
# Damage
# --------------------------------------------------------------------------


def weapon_projectiles_per_firing(
    item: Optional[Dict[str, Any]], modules: Optional[Sequence[Dict[str, Any]]] = None
) -> int:
    """Only bullet-class weapons and rocket launchers fire multiple projectiles."""
    projectile_class = str(_stats(item).get("projectileclass") or "").lower()
    if projectile_class != "bullet" and not is_rocket_launcher(item):
        return 1
    return max(1, int(effective_weapon_stats(item, modules)["numPerShot"]))


def weapon_base_direct_damage(
    data, item: Optional[Dict[str, Any]], modules: Optional[Sequence[Dict[str, Any]]] = None
) -> float:
    stats = effective_weapon_stats(item, modules)
    return stats["damage"] * stats["numFiring"] * weapon_projectiles_per_firing(item, modules)


def weapon_bonus_direct_damage(
    data, item: Optional[Dict[str, Any]], modules: Optional[Sequence[Dict[str, Any]]] = None
) -> float:
    stats = effective_weapon_stats(item, modules)
    bonus = always_applied_weapon_module_bonus(data, item)["damage"]
    return bonus * stats["numFiring"] * weapon_projectiles_per_firing(item, modules)


def weapon_direct_damage(
    data, item: Optional[Dict[str, Any]], modules: Optional[Sequence[Dict[str, Any]]] = None
) -> float:
    return weapon_base_direct_damage(data, item, modules) + weapon_bonus_direct_damage(
        data, item, modules
    )


def weapon_splash_damage(
    data, item: Optional[Dict[str, Any]], modules: Optional[Sequence[Dict[str, Any]]] = None
) -> float:
    """Splash for one side. The capacitor bonus is stated as total, so it halves."""
    splash_percent = max(0.0, finite_number(_stats(item).get("splashPercent")))
    return (
        weapon_base_direct_damage(data, item, modules) * splash_percent
        + weapon_bonus_direct_damage(data, item, modules) * splash_percent / 2
    )


def weapon_total_damage(
    data,
    item: Optional[Dict[str, Any]],
    include_splash: bool = True,
    modules: Optional[Sequence[Dict[str, Any]]] = None,
) -> float:
    """Damage from one trigger pull, counting splash on both sides."""
    direct = weapon_direct_damage(data, item, modules)
    if not include_splash:
        return direct
    return direct + weapon_splash_damage(data, item, modules) * 2


def weapon_heat(data, item: Optional[Dict[str, Any]]) -> float:
    return finite_number(_stats(item).get("heat")) + always_applied_weapon_module_bonus(
        data, item
    )["heat"]


# --------------------------------------------------------------------------
# Ammunition
# --------------------------------------------------------------------------

_AMMO_KEY_REPLACEMENTS = (
    ("hyperassaultgauss", "hag"),
    ("silverbulletgauss", "silverbullet"),
)
_LBX_PATTERN = re.compile(r"(lb\d+x)ac")


def ammo_capacity_quirk_key(item: Optional[Dict[str, Any]]) -> str:
    """Normalize an ammo item to the token used by `ammocapacity_*_additive` quirks."""
    key = normalize_lookup_key(_stats(item).get("type") or (item or {}).get("name"))
    key = key.replace("ammo", "")
    if key.startswith("clan"):
        key = "c" + key[len("clan") :]
    for source, target in _AMMO_KEY_REPLACEMENTS:
        key = key.replace(source, target)
    return _LBX_PATTERN.sub(r"\1", key)


def ammo_capacity_quirk_bonus(
    item: Optional[Dict[str, Any]], quirks: Optional[Iterable[Dict[str, Any]]] = None
) -> float:
    if (item or {}).get("item_type") != "ammo":
        return 0.0
    ammo_key = ammo_capacity_quirk_key(item)
    if not ammo_key:
        return 0.0
    total = 0.0
    for quirk in quirks or ():
        name = str(quirk.get("name") or "").lower()
        if not name.startswith("ammocapacity_") or not name.endswith("_additive"):
            continue
        prefix = normalize_lookup_key(name[len("ammocapacity_") : -len("_additive")])
        if prefix == ammo_key:
            total += finite_number(quirk.get("value"))
    return total


def effective_ammo_shots(
    item: Optional[Dict[str, Any]], quirks: Optional[Iterable[Dict[str, Any]]] = None
) -> int:
    """Shots per ton of ammo, after any ammo-capacity quirks."""
    base_shots = max(0.0, finite_number(_stats(item).get("numShots")))
    capacity_bonus = ammo_capacity_quirk_bonus(item, quirks) * max(0.0, item_tons(item))
    return int(math.floor(base_shots + capacity_bonus + 0.000001))
