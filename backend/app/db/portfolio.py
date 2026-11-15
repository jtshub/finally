"""Positions, trade log, and atomic trade execution."""

import sqlite3

from app.db.connection import DEFAULT_USER, get_connection, new_id, now_iso, transaction

EPSILON = 1e-9


def get_positions(user_id: str = DEFAULT_USER) -> list[dict]:
    """Return all positions as {ticker, quantity, avg_cost, updated_at}, ordered by ticker."""
    with transaction() as conn:
        rows = conn.execute(
            "SELECT ticker, quantity, avg_cost, updated_at FROM positions "
            "WHERE user_id = ? ORDER BY ticker",
            (user_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_position(ticker: str, user_id: str = DEFAULT_USER) -> dict | None:
    """Return one position or None."""
    with transaction() as conn:
        return _get_position(conn, ticker, user_id)


def upsert_position(ticker: str, quantity: float, avg_cost: float, user_id: str = DEFAULT_USER) -> None:
    """Insert or update a position; quantity at (or near) zero deletes it."""
    with transaction() as conn:
        _upsert_position(conn, ticker, quantity, avg_cost, user_id)


def record_trade(ticker: str, side: str, quantity: float, price: float, user_id: str = DEFAULT_USER) -> dict:
    """Append a trade to the log and return it."""
    with transaction() as conn:
        return _insert_trade(conn, ticker, side, quantity, price, user_id)


def get_trades(user_id: str = DEFAULT_USER, limit: int = 50) -> list[dict]:
    """Return the most recent trades, newest first."""
    with transaction() as conn:
        rows = conn.execute(
            "SELECT id, ticker, side, quantity, price, executed_at FROM trades "
            "WHERE user_id = ? ORDER BY executed_at DESC, rowid DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
    return [dict(r) for r in rows]


def execute_trade_tx(ticker: str, side: str, quantity: float, price: float, user_id: str = DEFAULT_USER) -> dict:
    """Update cash, position and trade log in one transaction; return the trade.

    Buys use weighted-average cost; sells keep avg_cost. Raises ValueError on
    bad side/quantity, insufficient cash or insufficient shares.
    """
    if side not in ("buy", "sell"):
        raise ValueError(f"Invalid side: {side}")
    if quantity <= 0:
        raise ValueError("Quantity must be positive")
    conn = get_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")
        cash = conn.execute("SELECT cash_balance FROM users_profile WHERE id = ?", (user_id,)).fetchone()[0]
        pos = _get_position(conn, ticker, user_id)
        held, avg = (pos["quantity"], pos["avg_cost"]) if pos else (0.0, 0.0)
        cost = quantity * price
        if side == "buy":
            if cost > cash + EPSILON:
                raise ValueError(f"Insufficient cash: need ${cost:.2f}, have ${cash:.2f}")
            new_qty, new_avg, new_cash = held + quantity, (held * avg + cost) / (held + quantity), cash - cost
        else:
            if quantity > held + EPSILON:
                raise ValueError(f"Insufficient shares: have {held:g} {ticker}, tried to sell {quantity:g}")
            new_qty, new_avg, new_cash = held - quantity, avg, cash + cost
        conn.execute("UPDATE users_profile SET cash_balance = ? WHERE id = ?", (max(new_cash, 0.0), user_id))
        _upsert_position(conn, ticker, new_qty, new_avg, user_id)
        trade = _insert_trade(conn, ticker, side, quantity, price, user_id)
        conn.commit()
        return trade
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _get_position(conn: sqlite3.Connection, ticker: str, user_id: str) -> dict | None:
    row = conn.execute(
        "SELECT ticker, quantity, avg_cost, updated_at FROM positions WHERE user_id = ? AND ticker = ?",
        (user_id, ticker),
    ).fetchone()
    return dict(row) if row else None


def _upsert_position(conn: sqlite3.Connection, ticker: str, quantity: float, avg_cost: float, user_id: str) -> None:
    if quantity <= EPSILON:
        conn.execute("DELETE FROM positions WHERE user_id = ? AND ticker = ?", (user_id, ticker))
        return
    conn.execute(
        "INSERT INTO positions (id, user_id, ticker, quantity, avg_cost, updated_at) VALUES (?, ?, ?, ?, ?, ?) "
        "ON CONFLICT (user_id, ticker) DO UPDATE SET "
        "quantity = excluded.quantity, avg_cost = excluded.avg_cost, updated_at = excluded.updated_at",
        (new_id(), user_id, ticker, quantity, avg_cost, now_iso()),
    )


def _insert_trade(conn: sqlite3.Connection, ticker: str, side: str, quantity: float, price: float, user_id: str) -> dict:
    trade = {"id": new_id(), "ticker": ticker, "side": side, "quantity": quantity,
             "price": price, "executed_at": now_iso()}
    conn.execute(
        "INSERT INTO trades (id, user_id, ticker, side, quantity, price, executed_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (trade["id"], user_id, ticker, side, quantity, price, trade["executed_at"]),
    )
    return trade
