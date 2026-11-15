"""SQLite connection management, lazy schema creation and seeding."""

import os
import sqlite3
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
DB_PATH = os.environ.get("FINALLY_DB_PATH", str(REPO_ROOT / "db" / "finally.db"))
SCHEMA_PATH = Path(__file__).with_name("schema.sql")

DEFAULT_USER = "default"
DEFAULT_CASH = 10000.0
DEFAULT_TICKERS = ["AAPL", "GOOGL", "MSFT", "AMZN", "TSLA", "NVDA", "META", "JPM", "V", "NFLX"]

_active_path = DB_PATH


def now_iso() -> str:
    """Current UTC time as an ISO 8601 string."""
    return datetime.now(UTC).isoformat()


def new_id() -> str:
    """New random UUID string for primary keys."""
    return str(uuid.uuid4())


def get_connection() -> sqlite3.Connection:
    """Open a new connection to the active database with dict-like rows."""
    conn = sqlite3.connect(_active_path)
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def transaction() -> Iterator[sqlite3.Connection]:
    """Yield a connection; commit on success, roll back on error, always close."""
    conn = get_connection()
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def init_db(path: str | None = None) -> None:
    """Point the module at `path` (default DB_PATH), create tables and seed if empty. Idempotent."""
    global _active_path
    _active_path = path or DB_PATH
    Path(_active_path).parent.mkdir(parents=True, exist_ok=True)
    with transaction() as conn:
        conn.executescript(SCHEMA_PATH.read_text())
        _seed(conn)


def _seed(conn: sqlite3.Connection) -> None:
    """Insert the default user and watchlist when the user profile is missing."""
    if conn.execute("SELECT 1 FROM users_profile WHERE id = ?", (DEFAULT_USER,)).fetchone():
        return
    ts = now_iso()
    conn.execute(
        "INSERT INTO users_profile (id, cash_balance, created_at) VALUES (?, ?, ?)",
        (DEFAULT_USER, DEFAULT_CASH, ts),
    )
    conn.executemany(
        "INSERT INTO watchlist (id, user_id, ticker, added_at) VALUES (?, ?, ?, ?)",
        [(new_id(), DEFAULT_USER, t, ts) for t in DEFAULT_TICKERS],
    )
