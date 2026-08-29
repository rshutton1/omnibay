"""The surface JavaScript calls through Pyodide.

Every bridge function returns a JSON string wrapping `{ok, data}` or
`{ok, error}`, so these tests also pin the contract the client depends on.
"""
import json
import os

import pytest

from omnibay import bridge

DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data"
)


@pytest.fixture(scope="module", autouse=True)
def initialised():
    bridge.init(DATA_DIR)


def unwrap(raw):
    envelope = json.loads(raw)
    assert envelope["ok"], envelope.get("error")
    return envelope["data"]


def error_of(raw):
    envelope = json.loads(raw)
    assert not envelope["ok"]
    return envelope["error"]


def test_everything_returns_a_json_string():
    """The boundary passes strings, never Python objects."""
    for raw in (
        bridge.meta(),
        bridge.list_mechs(),
        bridge.get_mech("hbk-4g"),
        bridge.list_equipment(),
        bridge.stock_build("hbk-4g"),
    ):
        assert isinstance(raw, str)
        json.loads(raw)


def test_init_reports_counts():
    data = unwrap(bridge.meta())
    assert data["counts"]["mechs"] == 1278
    assert "innersphere" in [f.lower() for f in data["factions"]]


def test_mech_index_covers_every_variant_in_browse_order():
    mechs = unwrap(bridge.list_mechs())
    assert len(mechs) == 1278
    weights = [m["weight_class"] for m in mechs]
    assert weights[0] == "light" and weights[-1] == "assault"
    assert all(m["hardpoints"] for m in mechs), "every variant should list hardpoints"


def test_get_mech_detail():
    mech = unwrap(bridge.get_mech("hbk-4g"))
    assert mech["display_name"] == "HBK-4G"
    assert mech["max_tons"] == 50
    assert mech["components"]["head"]["max_armor"] == 18
    assert mech["quirks"]


def test_omnimech_detail_uses_stock_pods():
    mech = unwrap(bridge.get_mech("tbr-prime"))
    assert mech["is_omnimech"] is True
    assert mech["hardpoints"] == {"ballistic": 2, "missile": 2, "energy": 5}
    assert mech["quirks"], "an omnimech's quirks come from its pods"


def test_stock_build_is_calculated():
    payload = unwrap(bridge.stock_build("hbk-4g"))
    assert payload["result"]["tonnage"]["used"] == 50.0
    assert payload["result"]["engine"]["rating"] == 200
    assert payload["result"]["warnings"] == []


def test_calculate_round_trips_a_posted_build():
    stock = unwrap(bridge.stock_build("hbk-4g"))["build"]
    result = unwrap(bridge.calculate("hbk-4g", json.dumps(stock)))["result"]
    assert result["tonnage"]["used"] == 50.0


def test_calculate_detects_an_overweight_build():
    stock = unwrap(bridge.stock_build("hbk-4g"))["build"]
    stock["components"]["left_arm"]["items"].append({"item_id": 1000, "weapon_group": None})
    result = unwrap(bridge.calculate("hbk-4g", json.dumps(stock)))["result"]
    assert result["tonnage"]["overweight"] is True
    assert result["warnings"]


def test_export_then_import():
    stock = unwrap(bridge.stock_build("hbk-4g"))["build"]
    code = unwrap(bridge.export_code("hbk-4g", json.dumps(stock)))["code"]
    assert code.startswith("A")

    imported = unwrap(bridge.import_code(code))
    assert imported["mech"]["name"] == "hbk-4g"
    assert imported["result"]["tonnage"]["used"] == 50.0


def test_equipment_catalogue():
    catalogue = unwrap(bridge.list_equipment())
    assert len(catalogue["equipment"]) == 751
    assert set(catalogue["upgrades"]) == {"armor", "structure", "heatsinks", "guidance"}


def test_errors_are_structured_not_raised():
    assert "Unknown mech" in error_of(bridge.get_mech("not-a-mech"))
    assert "not a supported MWO loadout code" in error_of(bridge.import_code("nonsense"))
    assert error_of(bridge.calculate("hbk-4g", "{not json"))


def test_engine_runs_without_the_optional_data_files(tmp_path):
    """The web bundle omits localization and skills; the engine must not care."""
    import shutil

    for name in ("index.json", "mechs.json", "equipment.json", "loadouts.json", "omnipods.json"):
        shutil.copy2(os.path.join(DATA_DIR, name), tmp_path / name)

    from omnibay.loader import GameData

    trimmed = GameData(str(tmp_path))
    assert len(trimmed.mechs) == 1278
    assert trimmed.localization == {}
    assert trimmed.skills == {}

    from omnibay.build import build_from_stock_loadout
    from omnibay.calculate import calculate_build

    mech = trimmed.mech_by_name("hbk-4g")
    build = build_from_stock_loadout(trimmed, mech)
    assert calculate_build(trimmed, mech, build)["tonnage"]["used"] == 50.0
