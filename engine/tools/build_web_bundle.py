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
# and the skill tree are loaded by the loader but unused by the current UI, so
# they stay out of the bundle until a feature needs them.
RUNTIME_DATA_FILES = (
    "index.json",
    "mechs.json",
    "equipment.json",
    "loadouts.json",
    "omnipods.json",
)

ENGINE_MODULES = (
    "__init__.py",
    "constants.py",
    "quirks.py",
    "items.py",
    "weapons.py",
    "codec.py",
    "loader.py",
    "build.py",
    "calculate.py",
    "bridge.py",
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

    for filename in ENGINE_MODULES:
        source = os.path.join(engine_source, filename)
        if not os.path.exists(source):
            print("missing engine module: {0}".format(filename), file=sys.stderr)
            return 1
        shutil.copy2(source, os.path.join(engine_out, filename))
    print("engine    {0} modules".format(len(ENGINE_MODULES)))

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
