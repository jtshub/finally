"""Pure portfolio valuation math (no DB, no cache)."""


def value_position(position: dict, price: float | None) -> dict:
    """Value one position; falls back to avg_cost when no live price is known."""
    quantity = position["quantity"]
    avg_cost = position["avg_cost"]
    current = price if price is not None else avg_cost
    pnl = (current - avg_cost) * quantity
    return {
        "ticker": position["ticker"],
        "quantity": quantity,
        "avg_cost": round(avg_cost, 4),
        "current_price": current,
        "market_value": round(current * quantity, 2),
        "unrealized_pnl": round(pnl, 2),
        "pnl_percent": round((current - avg_cost) / avg_cost * 100, 2) if avg_cost else 0.0,
    }


def value_portfolio(cash: float, positions: list[dict], prices: dict[str, float]) -> dict:
    """Build the GET /api/portfolio response from cash, positions and a price map."""
    valued = [value_position(p, prices.get(p["ticker"])) for p in positions]
    positions_value = float(sum(p["market_value"] for p in valued))
    return {
        "cash": round(cash, 2),
        "total_value": round(cash + positions_value, 2),
        "positions_value": round(positions_value, 2),
        "unrealized_pnl": round(float(sum(p["unrealized_pnl"] for p in valued)), 2),
        "positions": valued,
    }
