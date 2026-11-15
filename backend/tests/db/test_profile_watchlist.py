"""Tests for cash balance and watchlist functions."""

from app.db import (
    add_watchlist_ticker,
    get_cash,
    get_watchlist,
    remove_watchlist_ticker,
    set_cash,
)
from app.db.connection import DEFAULT_TICKERS


def test_cash_default_and_set():
    assert get_cash() == 10000.0
    set_cash(1234.5)
    assert get_cash() == 1234.5


def test_watchlist_seeded_in_order():
    assert get_watchlist() == DEFAULT_TICKERS


def test_add_appends_and_rejects_duplicate():
    assert add_watchlist_ticker("PYPL") is True
    assert get_watchlist()[-1] == "PYPL"
    assert add_watchlist_ticker("PYPL") is False
    assert get_watchlist().count("PYPL") == 1


def test_remove_present_and_absent():
    assert remove_watchlist_ticker("AAPL") is True
    assert "AAPL" not in get_watchlist()
    assert remove_watchlist_ticker("AAPL") is False
