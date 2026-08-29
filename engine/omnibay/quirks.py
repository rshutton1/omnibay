"""Quirk aggregation.

Direct port of the reference `public/quirk-calculations.js`. Quirk names are
suffixed by how they combine: `_multiplier` quirks sum into a single multiplier
around 1.0, `_additive` quirks sum into a flat offset. Nothing here knows about
specific mechs — callers hand in the quirk lists they have already collected
from the chassis, omnipods, set bonuses and skills.
"""
import re
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

Quirk = Mapping[str, Any]


def finite_number(value: Any, fallback: float = 0.0) -> float:
    """Coerce to float, falling back for None/NaN/non-numeric input."""
    if isinstance(value, bool):
        return fallback
    if isinstance(value, (int, float)):
        numeric = float(value)
        if numeric == numeric and numeric not in (float("inf"), float("-inf")):
            return numeric
    return fallback


def normalize_quirk_name(value: Any) -> str:
    return str(value or "").strip().lower()


def quirk_values(quirks: Optional[Iterable[Quirk]] = None) -> Dict[str, float]:
    """Collapse a quirk list into `{normalized_name: summed_value}`."""
    values: Dict[str, float] = {}
    for quirk in quirks or ():
        name = normalize_quirk_name(quirk.get("name"))
        if not name:
            continue
        values[name] = values.get(name, 0.0) + finite_number(quirk.get("value"))
    return values


class QuirkCollector:
    """Accumulates quirks while remembering where each contribution came from."""

    def __init__(self) -> None:
        self._entries: Dict[str, Dict[str, Any]] = {}

    def add(
        self,
        quirk: Quirk,
        source: str = "",
        **details: Any,
    ) -> None:
        key = normalize_quirk_name(quirk.get("name"))
        if not key:
            return
        entry = self._entries.get(key)
        if entry is None:
            entry = {
                "name": key,
                "display_name": quirk.get("display_name") or quirk.get("name"),
                "value": 0.0,
                "sources": [],
                "contributions": [],
            }
            self._entries[key] = entry
        value = finite_number(quirk.get("value"))
        entry["value"] += value
        if source and source not in entry["sources"]:
            entry["sources"].append(source)
        contribution = {
            "name": key,
            "display_name": quirk.get("display_name") or quirk.get("name"),
            "value": value,
            "source": source,
        }
        contribution.update(details)
        entry["contributions"].append(contribution)

    def extend(self, quirks: Iterable[Quirk], source: str = "") -> None:
        for quirk in quirks:
            self.add(quirk, source)

    def resolve(self) -> List[Dict[str, Any]]:
        """Return aggregated quirks sorted by display name, as the UI expects."""
        resolved = []
        for entry in self._entries.values():
            resolved.append(
                {
                    "name": entry["name"],
                    "display_name": entry["display_name"],
                    "value": entry["value"],
                    "value_text": quirk_value_text(entry["name"], entry["value"]),
                    "family": quirk_family(entry["name"]),
                    "beneficial": quirk_is_beneficial(entry["name"], entry["value"]),
                    "sources": list(entry["sources"]),
                    "source_text": ", ".join(entry["sources"]),
                    "contributions": list(entry["contributions"]),
                }
            )
        resolved.sort(key=lambda quirk: str(quirk["display_name"]))
        return resolved


# Quirk families where a lower number is the better outcome, so a negative
# value is a benefit rather than a penalty. Everything else reads the usual way.
LOWER_IS_BETTER_FAMILIES = frozenset(
    {
        "cooldown",
        "heat",
        "spread",
        "duration",
        "jamchance",
        "jamtime",
        "burntime",
        "overheatdamage",
        "receiving",
        "minheatpenaltylevel",
    }
)

# Most quirks are `<scope>_<family>_<mode>`, but a few carry no scope at all
# (`overheatdamage_multiplier`), so the leading underscore is optional.
_FAMILY_PATTERN = re.compile(r"(?:^|_)([a-z0-9]+)_(?:multiplier|additive)$")


def quirk_family(name: Any) -> str:
    """The stat a quirk acts on, e.g. `isautocannon20_cooldown_multiplier` -> `cooldown`."""
    match = _FAMILY_PATTERN.search(normalize_quirk_name(name))
    return match.group(1) if match else ""


def quirk_is_beneficial(name: Any, value: Any) -> Optional[bool]:
    """Whether a quirk helps the pilot. None when the value is zero or unreadable.

    Most quirks are better when positive, but cost-like families (heat,
    cooldown, spread, ...) are better when negative — a -15% cooldown quirk is
    an improvement, not a penalty.
    """
    numeric = finite_number(value, float("nan"))
    if numeric != numeric or numeric == 0:
        return None
    if quirk_family(name) in LOWER_IS_BETTER_FAMILIES:
        return numeric < 0
    return numeric > 0


def quirk_value_text(name: Any, value: Any) -> str:
    """Format a quirk for display: multipliers as percent, everything else flat."""
    numeric = finite_number(value, float("nan"))
    if numeric != numeric:
        return str(value)
    normalized = normalize_quirk_name(name)
    if normalized.endswith("_multiplier"):
        percent = numeric * 100
        text = "{0:.1f}".format(percent)
        if text.endswith(".0"):
            text = text[:-2]
        return "{0}{1}%".format("+" if percent > 0 else "", text)
    return "{0}{1}".format("+" if numeric > 0 else "", _trim(numeric))


def _trim(numeric: float) -> str:
    if numeric == int(numeric):
        return str(int(numeric))
    return str(numeric)


def quirk_filter_magnitude(name: Any, value: Any) -> Optional[float]:
    """Absolute effect size, used by the quirk filter's numeric threshold."""
    numeric = finite_number(value, float("nan"))
    if numeric != numeric:
        return None
    scale = 100 if normalize_quirk_name(name).endswith("_multiplier") else 1
    return abs(numeric * scale)


def quirk_add(values: Mapping[str, float], prefix: str, suffix: str) -> float:
    """Sum the `_all_additive` and `<suffix>_additive` variants of one quirk family."""
    prefix = normalize_quirk_name(prefix)
    suffix = normalize_quirk_name(suffix)
    return finite_number(values.get("{0}_all_additive".format(prefix))) + finite_number(
        values.get("{0}_{1}_additive".format(prefix, suffix))
    )


def quirk_multiplier(values: Mapping[str, float], names: Sequence[str]) -> float:
    """Combine multiplier quirks additively around 1.0, as MWO does."""
    return 1.0 + sum(finite_number(values.get(normalize_quirk_name(n))) for n in names)


def matching_quirk_value(quirks: Iterable[Quirk], name: str) -> float:
    expected = normalize_quirk_name(name)
    return sum(
        finite_number(q.get("value"))
        for q in quirks
        if normalize_quirk_name(q.get("name")) == expected
    )


def quirk_reduction(quirks: Iterable[Quirk], name: str) -> float:
    return max(0.0, -matching_quirk_value(quirks, name))


def quirk_increase(quirks: Iterable[Quirk], name: str) -> float:
    return max(0.0, matching_quirk_value(quirks, name))


def quirk_signed_value(quirks: Iterable[Quirk], name: str) -> float:
    return matching_quirk_value(quirks, name)


def is_harmful_duration_or_spread_quirk(quirk: Quirk) -> bool:
    """A positive spread/duration quirk is a penalty, so it displays as harmful."""
    if not finite_number(quirk.get("value")) > 0:
        return False
    name = normalize_quirk_name(quirk.get("name"))
    if name.endswith("_spread_multiplier"):
        return True
    return name.endswith("_duration_multiplier") and "narc" not in name


def durability_skill_final_value(value: float, multiplier: Any) -> float:
    """Durability skills floor after applying, with an epsilon for float drift."""
    skill_multiplier = finite_number(multiplier)
    if skill_multiplier == 0:
        return value
    import math

    return math.floor(value * (1 + skill_multiplier) + 1e-9)
