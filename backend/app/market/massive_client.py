"""Massive (Polygon.io) API client for real market data."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from datetime import date, timedelta

from massive import RESTClient
from massive.exceptions import BadResponse
from massive.rest.models import GroupedDailyAgg, SnapshotMarketType, TickerSnapshot

from .cache import PriceCache
from .interface import MarketDataSource

logger = logging.getLogger(__name__)


def snapshot_price(snap: TickerSnapshot) -> float | None:
    """Best available current price for a snapshot, by plan richness."""
    if snap.last_trade and snap.last_trade.price:
        return snap.last_trade.price
    if snap.min and snap.min.close:
        return snap.min.close
    if snap.day and snap.day.close:
        return snap.day.close
    if snap.prev_day and snap.prev_day.close:
        return snap.prev_day.close
    return None


class MassiveDataSource(MarketDataSource):
    """Polls Massive REST for all tracked tickers in one call per cycle.

    Modes:
      - "snapshot": full market snapshot (Starter+ plans), every poll_interval seconds
      - "eod": grouped daily closes, used automatically when the plan lacks
        snapshot access (free Basic); polled at most hourly
    """

    EOD_MIN_INTERVAL = 3600.0
    EOD_LOOKBACK_DAYS = 10

    def __init__(self, api_key: str, price_cache: PriceCache, poll_interval: float = 15.0) -> None:
        self._client = RESTClient(api_key=api_key)
        self._cache = price_cache
        self._interval = poll_interval
        self._tickers: list[str] = []
        self._mode = "snapshot"
        self._task: asyncio.Task | None = None

    async def start(self, tickers: list[str]) -> None:
        self._tickers = [t.upper().strip() for t in tickers]
        await self._poll_once()
        self._task = asyncio.create_task(self._poll_loop(), name="massive-poller")
        logger.info(
            "Massive poller started: %d tickers, %.1fs interval", len(self._tickers), self._interval
        )

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None

    async def add_ticker(self, ticker: str) -> None:
        ticker = ticker.upper().strip()
        if ticker not in self._tickers:
            self._tickers.append(ticker)

    async def remove_ticker(self, ticker: str) -> None:
        ticker = ticker.upper().strip()
        self._tickers = [t for t in self._tickers if t != ticker]
        self._cache.remove(ticker)

    def get_tickers(self) -> list[str]:
        return list(self._tickers)

    def _current_interval(self) -> float:
        """Sleep between polls for the current mode."""
        if self._mode == "eod":
            return max(self._interval, self.EOD_MIN_INTERVAL)
        return self._interval

    async def _poll_loop(self) -> None:
        """Poll forever. The first poll already happened in start()."""
        while True:
            await asyncio.sleep(self._current_interval())
            await self._poll_once()

    async def _poll_once(self) -> None:
        """One poll; errors are logged and retried next cycle."""
        if not self._tickers:
            return
        try:
            if self._mode == "snapshot":
                await asyncio.to_thread(self._poll_snapshots)
            else:
                await asyncio.to_thread(self._poll_eod)
        except BadResponse as e:
            if self._mode == "snapshot" and "NOT_AUTHORIZED" in str(e):
                logger.warning("Massive plan has no snapshot access; switching to end-of-day prices")
                self._mode = "eod"
                await self._poll_once()
            else:
                logger.error("Massive poll failed: %s", e)
        except Exception:
            logger.exception("Massive poll failed")

    def _poll_snapshots(self) -> None:
        """Fetch snapshots for all tickers in one call and write them to the cache."""
        snaps = self._client.get_snapshot_all(SnapshotMarketType.STOCKS, tickers=self._tickers)
        for snap in snaps:
            price = snapshot_price(snap)
            if price is None:
                continue
            self._cache.update(
                ticker=snap.ticker,
                price=price,
                timestamp=snap.updated / 1e9 if snap.updated else None,
                prev_close=snap.prev_day.close if snap.prev_day else None,
            )

    def _poll_eod(self) -> None:
        """Latest two daily closes from grouped-daily (walks back over non-trading days)."""
        wanted = set(self._tickers)
        days: list[dict[str, GroupedDailyAgg]] = []
        today = date.today()
        day = today
        while len(days) < 2 and day > today - timedelta(days=self.EOD_LOOKBACK_DAYS):
            bars = self._client.get_grouped_daily_aggs(day.isoformat())
            if bars:
                days.append({b.ticker: b for b in bars if b.ticker in wanted})
            day -= timedelta(days=1)
        latest, prior = (days + [{}, {}])[:2]
        for ticker, bar in latest.items():
            prev = prior.get(ticker)
            self._cache.update(
                ticker=ticker,
                price=bar.close,
                timestamp=bar.timestamp / 1000 if bar.timestamp else None,
                prev_close=prev.close if prev else None,
            )
