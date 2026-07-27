import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.pdca.store import Store  # noqa: E402


@pytest.fixture()
def store(tmp_path):
    return Store(tmp_path / "test.db")
