"""Watchlist tickers."""

import sqlite3

from app.db.connection import DEFAULT_USER, new_id, now_iso, transaction


def get_watchlist(user_id: str = DEFAULT_USER) -> list[str]:
    """Return watched tickers, oldest first."""
    with transaction() as conn:
        rows = conn.execute(
            "SELECT ticker FROM watchlist WHERE user_id = ? ORDER BY added_at, rowid", (user_id,)
        ).fetchall()
    return [r["ticker"] for r in rows]


def add_watchlist_ticker(ticker: str, user_id: str = DEFAULT_USER) -> bool:
    """Add a ticker; return False if it is already watched."""
    try:
        with transaction() as conn:
            conn.execute(
                "INSERT INTO watchlist (id, user_id, ticker, added_at) VALUES (?, ?, ?, ?)",
                (new_id(), user_id, ticker, now_iso()),
            )
    except sqlite3.IntegrityError:
        return False
    return True


def remove_watchlist_ticker(ticker: str, user_id: str = DEFAULT_USER) -> bool:
    """Remove a ticker; return False if it was not watched."""
    with transaction() as conn:
        cur = conn.execute("DELETE FROM watchlist WHERE user_id = ? AND ticker = ?", (user_id, ticker))
    return cur.rowcount > 0
