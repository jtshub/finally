"""Fixtures giving each test a fresh database in a temp dir."""

import pytest

from app.db import init_db


@pytest.fixture(autouse=True)
def db_path(tmp_path):
    """Initialize a fresh seeded database for each test."""
    path = str(tmp_path / "test.db")
    init_db(path)
    return path
