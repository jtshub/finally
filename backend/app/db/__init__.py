"""FinAlly persistence layer: stdlib sqlite3, plain functions, single default user."""

from app.db.connection import DB_PATH, get_connection, init_db
from app.db.history import add_chat_message, get_chat_messages, get_snapshots, record_snapshot
from app.db.portfolio import (
    execute_trade_tx,
    get_position,
    get_positions,
    get_trades,
    record_trade,
    upsert_position,
)
from app.db.profile import get_cash, set_cash
from app.db.watchlist import add_watchlist_ticker, get_watchlist, remove_watchlist_ticker

__all__ = [
    "DB_PATH",
    "add_chat_message",
    "add_watchlist_ticker",
    "execute_trade_tx",
    "get_cash",
    "get_chat_messages",
    "get_connection",
    "get_position",
    "get_positions",
    "get_snapshots",
    "get_trades",
    "get_watchlist",
    "init_db",
    "record_snapshot",
    "record_trade",
    "remove_watchlist_ticker",
    "set_cash",
    "upsert_position",
]
