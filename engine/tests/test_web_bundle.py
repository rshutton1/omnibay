"""The browser bundle must contain everything the engine needs.

The tests elsewhere run against the full `data/` directory, so a file the
engine reads but the bundle omits passes every test and then fails only in the
browser. That is exactly how the skill tree shipped empty, so this asserts the
bundle's contents directly.
"""
import json
import os
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BUNDLER = os.path.join(ROOT, "engine", "tools", "build_web_bundle.py")


@pytest.fixture(scope="module")
def bundle(tmp_path_factory):
    out = tmp_path_factory.mktemp("bundle")
    subprocess.run(
        [sys.executable, BUNDLER, "--out", str(out)], check=True, capture_output=True
    )
    return out


def test_manifest_lists_modules_and_data(bundle):
    with open(bundle / "engine" / "manifest.json", encoding="utf-8") as handle:
        manifest = json.load(handle)
    assert manifest["modules"]
    assert manifest["data"]


def test_every_manifest_entry_actually_exists(bundle):
    """A manifest naming a missing file fails in the browser, not here."""
    with open(bundle / "engine" / "manifest.json", encoding="utf-8") as handle:
        manifest = json.load(handle)

    missing = [m for m in manifest["modules"] if not (bundle / "engine" / "omnibay" / m).exists()]
    missing += [d for d in manifest["data"] if not (bundle / "data" / d).exists()]
    assert not missing


def test_manifest_covers_every_engine_module(bundle):
    """Adding a module must not require remembering to list it."""
    source = os.path.join(ROOT, "engine", "omnibay")
    expected = {f for f in os.listdir(source) if f.endswith(".py")}
    with open(bundle / "engine" / "manifest.json", encoding="utf-8") as handle:
        assert set(json.load(handle)["modules"]) == expected


def test_bundled_data_supports_every_engine_feature(bundle):
    """Load the engine against only the bundled data and exercise each feature."""
    from omnibay.build import build_from_stock_loadout
    from omnibay.calculate import calculate_build
    from omnibay.loader import GameData
    from omnibay.skills import skill_tree
    from omnibay.weapon_stats import weapon_tooltip

    data = GameData(str(bundle / "data"))
    assert len(data.mechs) == 1278
    assert data.skills.get("categories"), "skill tree needs skills.json in the bundle"

    mech = data.mech_by_name("hbk-4g")
    build = build_from_stock_loadout(data, mech)

    assert calculate_build(data, mech, build)["tonnage"]["used"] == 50.0
    assert weapon_tooltip(data, data.item(1000), [])["name"] == "AC/20"

    assert data.skill_graph.get("nodes"), "skill graph needs skill-graph.json in the bundle"
    tree = skill_tree(data, mech, build, [])
    assert len(tree["categories"]) == 7
    assert sum(len(c["nodes"]) for c in tree["categories"]) == 239
    assert sum(len(c["edges"]) for c in tree["categories"]) == 197
