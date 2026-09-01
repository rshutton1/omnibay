"""Assemble the static web bundle.

Run from the repository root (or via `npm run build`). This copies the engine
and the game data into the frontend's public directory, and precomputes the
mech index so the browser view can render before Pyodide has finished booting.

    python engine/tools/build_web_bundle.py [--out frontend/public]
"""
import argparse
import json
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "engine"))

from omnibay import bridge  # noqa: E402
from omnibay.loader import GameData  # noqa: E402

# Only the files the engine actually reads at runtime. Localization (1.6 MB)
# stays out until the UI needs it; the loader treats it as optional.
RUNTIME_DATA_FILES = (
    "index.json",
    "mechs.json",
    "equipment.json",
    "loadouts.json",
    "omnipods.json",
    "skills.json",
)

def engine_modules(engine_source: str) -> list:
    """Every Python module in the engine package.

    Discovered rather than listed: a hardcoded list silently omits new modules,
    which surfaces in the browser as an import failure rather than a build
    error. The manifest written alongside them lets the client stage exactly
    this set without repeating it.
    """
    return sorted(
        name
        for name in os.listdir(engine_source)
        if name.endswith(".py") and not name.startswith(".")
    )


def _megabytes(path: str) -> float:
    return os.path.getsize(path) / 1048576


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        default=os.path.join(ROOT, "frontend", "public"),
        help="Directory to write the bundle into (default: frontend/public)",
    )
    args = parser.parse_args()

    data_source = os.path.join(ROOT, "data")
    engine_source = os.path.join(ROOT, "engine", "omnibay")
    data_out = os.path.join(args.out, "data")
    engine_out = os.path.join(args.out, "engine", "omnibay")

    for directory in (data_out, engine_out):
        shutil.rmtree(directory, ignore_errors=True)
        os.makedirs(directory)

    total = 0.0
    for filename in RUNTIME_DATA_FILES:
        source = os.path.join(data_source, filename)
        if not os.path.exists(source):
            print("missing required data file: {0}".format(filename), file=sys.stderr)
            return 1
        shutil.copy2(source, os.path.join(data_out, filename))
        total += _megabytes(source)
    print("data      {0} files, {1:.1f} MB".format(len(RUNTIME_DATA_FILES), total))

    modules = engine_modules(engine_source)
    if "bridge.py" not in modules:
        print("engine package has no bridge.py", file=sys.stderr)
        return 1
    for filename in modules:
        shutil.copy2(os.path.join(engine_source, filename), os.path.join(engine_out, filename))

    # The client stages both the engine and the game data from this manifest,
    # so neither list can drift out of step with what was actually bundled.
    manifest_path = os.path.join(args.out, "engine", "manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as handle:
        json.dump({"modules": modules, "data": list(RUNTIME_DATA_FILES)}, handle)
    print("engine    {0} modules".format(len(modules)))

    # Precomputed so the mech browser needs no Python at all.
    data = GameData(data_source)
    index = {
        "meta": bridge.summary_payload(data),
        "mechs": bridge.mech_index(data),
    }
    index_path = os.path.join(args.out, "mech-index.json")
    with open(index_path, "w", encoding="utf-8") as handle:
        json.dump(index, handle, separators=(",", ":"))
    print(
        "index     {0} variants, {1:.2f} MB".format(
            len(index["mechs"]), _megabytes(index_path)
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
