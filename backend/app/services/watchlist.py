"""Watchlist reads and changes, kept in sync with the market data source."""

import re

from app import db
from app.market import MarketDataSource, PriceCache, normalize_ticker

TICKER_RE = re.compile(r"^[A-Z][A-Z0-9.\-]{0,9}$")


class NotInWatchlistError(LookupError):
    """Raised when removing a ticker that is not on the watchlist."""


def get_watchlist(cache: PriceCache) -> list[dict]:
    """Watchlist tickers with latest prices (price fields None until first tick)."""
    return [_row(t, cache) for t in db.get_watchlist()]


def _row(ticker: str, cache: PriceCache) -> dict:
    u = cache.get(ticker)
    return {
        "ticker": ticker,
        "price": u.price if u else None,
        "previous_price": u.previous_price if u else None,
        "change_percent": u.change_percent if u else None,
        "day_change_percent": u.day_change_percent if u else None,
        "direction": u.direction if u else None,
    }


async def add_ticker(source: MarketDataSource, ticker: str) -> str:
    """Add a ticker to the watchlist and the market source; raises ValueError if invalid/present."""
    ticker = normalize_ticker(ticker)
    if not TICKER_RE.match(ticker):
        raise ValueError(f"Invalid ticker '{ticker}'")
    if not db.add_watchlist_ticker(ticker):
        raise ValueError(f"{ticker} is already in the watchlist")
    await source.add_ticker(ticker)
    return ticker


async def remove_ticker(source: MarketDataSource, ticker: str) -> str:
    """Remove a ticker; keeps it streaming if a position still holds it."""
    ticker = normalize_ticker(ticker)
    if not db.remove_watchlist_ticker(ticker):
        raise NotInWatchlistError(f"{ticker} is not in the watchlist")
    if db.get_position(ticker) is None:
        await source.remove_ticker(ticker)
    return ticker
