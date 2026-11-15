"""Tests for schema creation and seeding."""

from app.db import get_connection, init_db
from app.db.connection import DEFAULT_TICKERS

TABLES = {"users_profile", "watchlist", "positions", "trades", "portfolio_snapshots", "chat_messages"}


def test_creates_all_tables():
    with get_connection() as conn:
        rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    assert TABLES <= {r["name"] for r in rows}


def test_seeds_default_user_and_watchlist():
    with get_connection() as conn:
        user = conn.execute("SELECT * FROM users_profile").fetchall()
        tickers = conn.execute("SELECT ticker FROM watchlist ORDER BY rowid").fetchall()
    assert [(u["id"], u["cash_balance"]) for u in user] == [("default", 10000.0)]
    assert [t["ticker"] for t in tickers] == DEFAULT_TICKERS


def test_init_is_idempotent(db_path):
    init_db(db_path)
    init_db(db_path)
    with get_connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM users_profile").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM watchlist").fetchone()[0] == 10


def test_creates_parent_directory(tmp_path):
    path = tmp_path / "nested" / "dir" / "x.db"
    init_db(str(path))
    assert path.exists()
