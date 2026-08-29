import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from omnibay.loader import get_game_data  # noqa: E402

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")


@pytest.fixture(scope="session")
def data():
    return get_game_data()


@pytest.fixture(scope="session")
def stock_build_expectations():
    """Expected values captured from the reference MwoLab client."""
    with open(os.path.join(FIXTURES, "stock_builds.json"), encoding="utf-8") as handle:
        return json.load(handle)
