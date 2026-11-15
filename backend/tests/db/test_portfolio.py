"""Tests for positions, trade log and atomic trade execution."""

import pytest

from app.db import (
    execute_trade_tx,
    get_cash,
    get_position,
    get_positions,
    get_trades,
    record_trade,
    set_cash,
    upsert_position,
)


def test_upsert_insert_update_delete():
    upsert_position("AAPL", 5, 100.0)
    upsert_position("AAPL", 7, 110.0)
    assert get_position("AAPL")["quantity"] == 7
    assert get_position("AAPL")["avg_cost"] == 110.0
    upsert_position("AAPL", 0, 110.0)
    assert get_position("AAPL") is None


def test_get_positions_sorted():
    upsert_position("MSFT", 1, 1.0)
    upsert_position("AAPL", 2, 2.0)
    assert [p["ticker"] for p in get_positions()] == ["AAPL", "MSFT"]
    assert set(get_positions()[0]) == {"ticker", "quantity", "avg_cost", "updated_at"}


def test_record_and_get_trades_newest_first():
    t1 = record_trade("AAPL", "buy", 1, 100.0)
    t2 = record_trade("AAPL", "sell", 1, 101.0)
    assert set(t1) == {"id", "ticker", "side", "quantity", "price", "executed_at"}
    assert [t["id"] for t in get_trades()] == [t2["id"], t1["id"]]
    assert len(get_trades(limit=1)) == 1


def test_buy_updates_cash_position_and_log():
    trade = execute_trade_tx("AAPL", "buy", 10, 100.0)
    assert get_cash() == 9000.0
    assert get_position("AAPL")["quantity"] == 10
    assert get_trades()[0]["id"] == trade["id"]


def test_buy_weighted_average_cost():
    execute_trade_tx("AAPL", "buy", 10, 100.0)
    execute_trade_tx("AAPL", "buy", 30, 200.0)
    pos = get_position("AAPL")
    assert pos["quantity"] == 40
    assert pos["avg_cost"] == pytest.approx(175.0)


def test_sell_keeps_avg_cost_and_adds_cash():
    execute_trade_tx("AAPL", "buy", 10, 100.0)
    execute_trade_tx("AAPL", "sell", 4, 80.0)
    pos = get_position("AAPL")
    assert pos["quantity"] == 6
    assert pos["avg_cost"] == 100.0
    assert get_cash() == pytest.approx(9000.0 + 320.0)


def test_sell_all_deletes_position():
    execute_trade_tx("AAPL", "buy", 0.3, 100.0)
    execute_trade_tx("AAPL", "sell", 0.1, 100.0)
    execute_trade_tx("AAPL", "sell", 0.2, 100.0)  # 0.3 - 0.1 leaves float dust
    assert get_position("AAPL") is None
    assert get_cash() == pytest.approx(10000.0)


def test_buy_exact_cash_with_dust():
    set_cash(0.3)
    execute_trade_tx("X", "buy", 3, 0.1)  # 3 * 0.1 = 0.30000000000000004
    assert get_cash() == 0.0


def test_insufficient_cash_rolls_back():
    with pytest.raises(ValueError, match="Insufficient cash"):
        execute_trade_tx("AAPL", "buy", 1000, 100.0)
    assert get_cash() == 10000.0
    assert get_position("AAPL") is None
    assert get_trades() == []


def test_insufficient_shares_rolls_back():
    execute_trade_tx("AAPL", "buy", 1, 100.0)
    with pytest.raises(ValueError, match="Insufficient shares"):
        execute_trade_tx("AAPL", "sell", 2, 100.0)
    assert get_position("AAPL")["quantity"] == 1
    assert len(get_trades()) == 1


def test_sell_unowned_raises():
    with pytest.raises(ValueError, match="Insufficient shares"):
        execute_trade_tx("TSLA", "sell", 1, 100.0)


@pytest.mark.parametrize(("side", "qty"), [("hold", 1), ("buy", 0), ("sell", -1)])
def test_invalid_side_or_quantity(side, qty):
    with pytest.raises(ValueError):
        execute_trade_tx("AAPL", side, qty, 100.0)
