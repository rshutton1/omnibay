"""Per-item accessors.

Thin, total functions over raw equipment dicts. They tolerate missing stats
because the extracted data is not uniformly populated across item families.
"""
from typing import Any, Dict, Optional

from omnibay.constants import AMS_HARDPOINT_TYPE_ID
from omnibay.quirks import finite_number

Item = Dict[str, Any]


def _stats(item: Optional[Item]) -> Dict[str, Any]:
    if not item:
        return {}
    return item.get("stats") or {}


def item_tons(item: Optional[Item]) -> float:
    """Tonnage. Engines express a signed offset in `weight` rather than `tons`."""
    stats = _stats(item)
    if "tons" in stats:
        return finite_number(stats.get("tons"))
    return finite_number(stats.get("weight"))


def item_slots(item: Optional[Item]) -> int:
    return int(finite_number(_stats(item).get("slots")))


def item_heat(item: Optional[Item]) -> float:
    return finite_number(_stats(item).get("heat"))


def item_health(item: Optional[Item]) -> float:
    stats = _stats(item)
    return finite_number(stats.get("health", stats.get("Health")))


def item_type(item: Optional[Item]) -> str:
    return str((item or {}).get("item_type") or "")


def is_engine(item: Optional[Item]) -> bool:
    return item_type(item) == "engine"


def is_weapon(item: Optional[Item]) -> bool:
    return item_type(item) == "weapon"


def is_ammo(item: Optional[Item]) -> bool:
    return item_type(item) == "ammo"


def is_jump_jet(item: Optional[Item]) -> bool:
    return item_type(item) == "jumpjet"


def is_heat_sink(item: Optional[Item]) -> bool:
    """Heat sinks are identified by ctype, with a name fallback for odd entries."""
    if not item:
        return False
    if item.get("ctype") == "CHeatSinkStats":
        return True
    return "heatsink" in str(item.get("name") or "").lower()


def is_ams_weapon(item: Optional[Item]) -> bool:
    stats = _stats(item)
    return str(stats.get("type") or "").lower() == "ams" or "ams" in str(
        (item or {}).get("name") or ""
    ).lower()


def is_guidance_weapon(item: Optional[Item]) -> bool:
    """A launcher that can be swapped between standard and Artemis guidance.

    Launchers that always carry Artemis are excluded — they have no counterpart
    to switch to, so the upgrade costs them nothing extra.
    """
    if not is_weapon(item):
        return False
    stats = _stats(item)
    return bool(stats.get("artemisAmmoType")) and not finite_number(
        stats.get("alwaysHasArtemis")
    )


def is_artemis_weapon(item: Optional[Item]) -> bool:
    """The Artemis variant is a distinct item, not a flag on the base launcher."""
    return is_guidance_weapon(item) and "artemis" in str((item or {}).get("name") or "").lower()


def engine_rating(item: Optional[Item]) -> int:
    return int(finite_number(_stats(item).get("rating")))


def engine_side_slots(item: Optional[Item]) -> int:
    return max(0, int(finite_number(_stats(item).get("sideSlots"))))


def engine_included_heat_sinks(item: Optional[Item]) -> int:
    """Engines carry up to 10 internal heat sinks for free."""
    if not item:
        return 0
    return min(10, int(finite_number(_stats(item).get("heatsinks"))))


def engine_additional_heat_sink_capacity(item: Optional[Item]) -> int:
    """Additional heat sinks that fit inside the engine, beyond the included ten."""
    if not item:
        return 0
    return max(0, int(finite_number(_stats(item).get("heatsinks"))) - 10)


def ammo_shots(item: Optional[Item]) -> float:
    return finite_number(_stats(item).get("numShots"))


def equipment_hardpoint_type(item: Optional[Item]) -> str:
    """The hardpoint an item consumes, or '' if it needs none."""
    if not item:
        return ""
    if is_weapon(item):
        if is_ams_weapon(item):
            return "ams"
        return str(_stats(item).get("type") or "").lower()
    return ""


def hardpoint_type(hardpoint: Optional[Dict[str, Any]]) -> str:
    """`Type: 4` marks AMS regardless of the extracted label."""
    if not hardpoint:
        return ""
    if str(hardpoint.get("Type")) == AMS_HARDPOINT_TYPE_ID:
        return "ams"
    return str(hardpoint.get("hardpoint_type") or "").lower()


def hardpoint_slots(hardpoint: Optional[Dict[str, Any]]) -> int:
    return max(1, int(finite_number((hardpoint or {}).get("weapon_slots"), 1)))


def internal_item_tonnage_modifier(item: Optional[Item]) -> float:
    """Compact Gyro tonnage is an added penalty over the standard gyro."""
    tons = item_tons(item)
    name = str((item or {}).get("name") or "").strip().lower().replace(" ", "")
    if name.startswith("compactgyro"):
        return abs(tons)
    return tons


def item_display_name(item: Optional[Item]) -> str:
    if not item:
        return ""
    return str(item.get("display_name") or item.get("name") or "")


def item_matches_faction(item: Optional[Item], faction: str) -> bool:
    """Empty faction on an item means it is available to everyone."""
    from omnibay.loader import normalize_faction

    raw = str((item or {}).get("faction") or "")
    if not raw:
        return True
    wanted = normalize_faction(faction)
    if not wanted:
        return True
    return wanted in [normalize_faction(part) for part in raw.split(",")]
