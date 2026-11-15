"""Portfolio reads, trade execution and snapshots (DB + live price cache)."""

import asyncio
import logging

from app import db
from app.market import PriceCache, normalize_ticker
from app.services.valuation import value_portfolio

logger = logging.getLogger(__name__)

SNAPSHOT_INTERVAL = 30.0


def get_portfolio(cache: PriceCache) -> dict:
    """Current portfolio valued at live cache prices."""
    prices = {t: u.price for t, u in cache.get_all().items()}
    return value_portfolio(db.get_cash(), db.get_positions(), prices)


def execute_trade(cache: PriceCache, ticker: str, side: str, quantity: float) -> dict:
    """Validate and execute a market order at the cached price; raises ValueError on bad input."""
    ticker = normalize_ticker(ticker)
    if side not in ("buy", "sell"):
        raise ValueError(f"Invalid side '{side}': must be 'buy' or 'sell'")
    if quantity <= 0:
        raise ValueError("Quantity must be positive")
    price = cache.get_price(ticker)
    if price is None:
        raise ValueError(f"No live price for {ticker}; add it to the watchlist first")
    trade = db.execute_trade_tx(ticker, side, quantity, price)
    record_snapshot(cache)
    return trade


def record_snapshot(cache: PriceCache) -> None:
    """Store the current total portfolio value."""
    db.record_snapshot(get_portfolio(cache)["total_value"])


def get_history() -> list[dict]:
    """Portfolio value snapshots, oldest first."""
    return [
        {"total_value": s["total_value"], "recorded_at": s["recorded_at"]}
        for s in db.get_snapshots()
    ]


async def snapshot_loop(cache: PriceCache, interval: float = SNAPSHOT_INTERVAL) -> None:
    """Record a snapshot every `interval` seconds until cancelled."""
    while True:
        await asyncio.sleep(interval)
        try:
            record_snapshot(cache)
        except Exception:
            logger.exception("Portfolio snapshot failed")
