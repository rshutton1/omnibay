"""The surface JavaScript calls.

Everything crosses the WASM boundary as a JSON string. That is deliberate:
handing Pyodide proxy objects to JS means the caller has to remember to destroy
them, and deeply nested dicts marshal slowly. One `json.dumps` is simpler and
measurably cheap.

Each function returns `{"ok": true, "data": ...}` or `{"ok": false, "error": ...}`
so the client never has to catch a Python exception through the bridge.
"""
import json
import traceback
from typing import Any, Callable, Dict, List, Optional

from omnibay import build as B
from omnibay import codec
from omnibay import items as I
from omnibay.calculate import calculate_build
from omnibay.constants import COMPONENT_ORDER, WEIGHT_CLASS_ORDER
from omnibay.loader import GameData
from omnibay.quirks import finite_number

_data: Optional[GameData] = None


def _ok(payload: Any) -> str:
    return json.dumps({"ok": True, "data": payload})


def _err(message: str, detail: str = "") -> str:
    return json.dumps({"ok": False, "error": message, "detail": detail})


def _guard(function: Callable[..., str]) -> Callable[..., str]:
    """Turn any unexpected exception into a structured error rather than a trap."""

    def wrapper(*args: Any, **kwargs: Any) -> str:
        try:
            return function(*args, **kwargs)
        except Exception as error:  # noqa: BLE001 - the boundary must not leak
            return _err(str(error) or error.__class__.__name__, traceback.format_exc())

    wrapper.__name__ = function.__name__
    wrapper.__doc__ = function.__doc__
    return wrapper


def _require_data() -> GameData:
    if _data is None:
        raise RuntimeError("Engine not initialised - call init() first.")
    return _data


def _require_mech(reference: Any) -> Dict[str, Any]:
    mech = _require_data().mech(reference)
    if not mech:
        raise LookupError("Unknown mech: {0}".format(reference))
    return mech


# --------------------------------------------------------------------------
# Lifecycle
# --------------------------------------------------------------------------


@_guard
def init(data_dir: str = "/data") -> str:
    """Load and index the game data. Call once, before anything else."""
    global _data
    _data = GameData(data_dir)
    return _ok(summary_payload(_data))


def summary_payload(data: GameData) -> Dict[str, Any]:
    payload = data.summary()
    payload["weight_classes"] = list(WEIGHT_CLASS_ORDER)
    payload["factions"] = sorted({mech["faction"] for mech in data.mechs})
    return payload


@_guard
def meta() -> str:
    return _ok(summary_payload(_require_data()))


# --------------------------------------------------------------------------
# Mechs
# --------------------------------------------------------------------------


def stock_hardpoints(data: GameData, mech: Dict[str, Any]) -> Dict[str, int]:
    """Hardpoint totals for the variant as it ships.

    An omnimech carries no hardpoints on its chassis - they come from the pods
    in its stock loadout - so the stock pods are resolved before counting.
    """
    definition = mech.get("definition") or {}
    stock_components = data.stock_loadout_for(mech).get("components") or {}

    totals: Dict[str, int] = {}
    for name, component in (definition.get("components") or {}).items():
        pod = data.omnipod(_stock_omnipod_id((stock_components.get(name) or {}).get("omnipod")))
        source = pod if pod else component
        for hardpoint in source.get("hardpoints") or ():
            hp_type = I.hardpoint_type(hardpoint)
            if hp_type:
                totals[hp_type] = totals.get(hp_type, 0) + I.hardpoint_slots(hardpoint)
    return totals


def _stock_omnipod_id(value: Any) -> Optional[int]:
    """The extracted data writes the string "none" for battlemechs."""
    try:
        numeric = int(value)
    except (TypeError, ValueError):
        return None
    return numeric if numeric > 0 else None


def mech_summary(data: GameData, mech: Dict[str, Any]) -> Dict[str, Any]:
    stats = (mech.get("definition") or {}).get("stats") or {}
    return {
        "id": mech["id"],
        "name": mech["name"],
        "display_name": mech["display_name"],
        "chassis": mech["chassis"],
        "faction": mech["faction"],
        "weight_class": mech["weight_class"],
        "max_tons": finite_number(stats.get("MaxTons")),
        "is_omnimech": B.has_fixed_omnipods(data, mech),
        "hardpoints": stock_hardpoints(data, mech),
        "jump_jets": int(finite_number(stats.get("MaxJumpJets"))),
        "engine_range": [
            int(finite_number(stats.get("MinEngineRating"))),
            int(finite_number(stats.get("MaxEngineRating"))),
        ],
    }


def mech_index(data: GameData) -> List[Dict[str, Any]]:
    """Every variant's summary, in browse order.

    Emitted at build time so the mech browser can render before the engine has
    finished booting.
    """
    summaries = [mech_summary(data, mech) for mech in data.mechs]
    summaries.sort(
        key=lambda m: (
            WEIGHT_CLASS_ORDER.index(m["weight_class"])
            if m["weight_class"] in WEIGHT_CLASS_ORDER
            else len(WEIGHT_CLASS_ORDER),
            m["max_tons"],
            m["display_name"],
        )
    )
    return summaries


@_guard
def list_mechs() -> str:
    return _ok(mech_index(_require_data()))


@_guard
def get_mech(reference: str) -> str:
    data = _require_data()
    mech = _require_mech(reference)
    raw = mech.get("definition") or {}

    # Describe the variant as it ships: for an omnimech that means its stock
    # pods, which carry the hardpoints and most of the quirks.
    stock = B.build_from_stock_loadout(data, mech)
    definition = B.effective_definition(data, mech, stock)

    return _ok(
        dict(
            mech_summary(data, mech),
            stats=raw.get("stats") or {},
            movement=raw.get("movement") or {},
            quirks=B.effective_quirks(data, mech, stock),
            components={
                name: {
                    "slots": (definition.get("components") or {}).get(name, {}).get("slots"),
                    "hp": (definition.get("components") or {}).get(name, {}).get("hp"),
                    "hardpoints": (definition.get("components") or {})
                    .get(name, {})
                    .get("hardpoints")
                    or [],
                    "max_armor": B.base_max_armor(mech, name),
                }
                for name in COMPONENT_ORDER
            },
        )
    )


@_guard
def get_omnipods(reference: str) -> str:
    data = _require_data()
    mech = _require_mech(reference)
    pods: Dict[str, List[Dict[str, Any]]] = {}
    for pod in data.omnipods_for(mech.get("chassis")):
        component = str(pod.get("component") or "")
        pods.setdefault(component, []).append(
            {
                "id": pod.get("id"),
                "set": pod.get("set"),
                "component": component,
                "hardpoints": [
                    {"type": I.hardpoint_type(hp), "slots": I.hardpoint_slots(hp)}
                    for hp in pod.get("hardpoints") or ()
                ],
                "quirks": pod.get("quirks") or [],
                "set_bonuses": pod.get("set_bonuses") or [],
            }
        )
    return _ok({"chassis": mech.get("chassis"), "components": pods})


# --------------------------------------------------------------------------
# Equipment
# --------------------------------------------------------------------------


def equipment_catalogue(data: GameData) -> List[Dict[str, Any]]:
    results = [
        {
            "id": item["id"],
            "name": item["name"],
            "display_name": I.item_display_name(item),
            "item_type": item.get("item_type"),
            "family": item.get("family"),
            "faction": item.get("faction"),
            "slots": I.item_slots(item),
            "tons": I.item_tons(item),
            "heat": I.item_heat(item),
            "hardpoint_type": I.equipment_hardpoint_type(item),
            "stats": item.get("stats") or {},
        }
        for item in data.items.values()
    ]
    results.sort(key=lambda i: (str(i["item_type"]), i["display_name"]))
    return results


def upgrade_catalogue(data: GameData) -> Dict[str, List[Dict[str, Any]]]:
    return {
        category: [
            {
                "id": item["id"],
                "display_name": I.item_display_name(item),
                "faction": item.get("faction"),
                "stats": item.get("stats") or {},
            }
            for item in data.upgrade_items(category)
        ]
        for category in ("armor", "structure", "heatsinks", "guidance")
    }


@_guard
def list_equipment() -> str:
    data = _require_data()
    return _ok({"equipment": equipment_catalogue(data), "upgrades": upgrade_catalogue(data)})


# --------------------------------------------------------------------------
# Builds
# --------------------------------------------------------------------------


@_guard
def stock_build(reference: str) -> str:
    data = _require_data()
    mech = _require_mech(reference)
    build = B.build_from_stock_loadout(data, mech)
    return _ok({"build": build, "result": calculate_build(data, mech, build)})


@_guard
def calculate(reference: str, build_json: str) -> str:
    """Recalculate a build. This is the hot path - called on every edit."""
    data = _require_data()
    mech = _require_mech(reference)
    build = json.loads(build_json)
    B.apply_fixed_omnipods(data, mech, build)
    return _ok({"build": build, "result": calculate_build(data, mech, build)})


@_guard
def export_code(reference: str, build_json: str) -> str:
    data = _require_data()
    mech = _require_mech(reference)
    return _ok({"code": B.build_to_mwo_code(data, mech, json.loads(build_json))})


@_guard
def import_code(code: str) -> str:
    data = _require_data()
    try:
        decoded = codec.decode(code)
    except codec.MwoCodecError as error:
        return _err(str(error))

    mech = data.mech(decoded["chassis_id"])
    if not mech:
        return _err("Unknown chassis id: {0}".format(decoded["chassis_id"]))

    try:
        build = B.build_from_decoded_code(data, mech, decoded)
    except codec.MwoCodecError as error:
        return _err(str(error))

    return _ok(
        {
            "mech": mech_summary(data, mech),
            "build": build,
            "result": calculate_build(data, mech, build),
        }
    )
