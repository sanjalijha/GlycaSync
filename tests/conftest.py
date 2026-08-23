import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db.database import Repository  # noqa: E402
from app.db.seed_data import seed  # noqa: E402


@pytest.fixture
def repo(tmp_path) -> Repository:
    """Isolated SQLite repository per test."""
    return Repository(db_path=tmp_path / "test.db")


@pytest.fixture
def seeded_repo(repo) -> Repository:
    seed(repo, force=True)
    return repo
