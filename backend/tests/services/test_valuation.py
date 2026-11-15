"""Tests for pure portfolio valuation."""

from app.services.valuation import value_portfolio, value_position


def test_empty_portfolio():
    result = value_portfolio(10000.0, [], {})
    assert result == {
        "cash": 10000.0,
        "total_value": 10000.0,
        "positions_value": 0.0,
        "unrealized_pnl": 0.0,
        "positions": [],
    }


def test_position_gain():
    p = value_position({"ticker": "AAPL", "quantity": 5, "avg_cost": 190.1}, 191.0)
    assert p["market_value"] == 955.0
    assert p["unrealized_pnl"] == 4.5
    assert p["pnl_percent"] == 0.47


def test_position_loss():
    p = value_position({"ticker": "TSLA", "quantity": 2, "avg_cost": 200.0}, 150.0)
    assert p["unrealized_pnl"] == -100.0
    assert p["pnl_percent"] == -25.0


def test_missing_price_uses_avg_cost():
    p = value_position({"ticker": "X", "quantity": 3, "avg_cost": 10.0}, None)
    assert p["current_price"] == 10.0
    assert p["unrealized_pnl"] == 0.0


def test_portfolio_totals():
    positions = [
        {"ticker": "AAPL", "quantity": 10, "avg_cost": 100.0},
        {"ticker": "MSFT", "quantity": 0.5, "avg_cost": 400.0},
    ]
    result = value_portfolio(5000.0, positions, {"AAPL": 110.0, "MSFT": 380.0})
    assert result["positions_value"] == 1290.0
    assert result["total_value"] == 6290.0
    assert result["unrealized_pnl"] == 90.0
