"""Massive (Polygon.io) API client for real market data."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import threading
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from massive import RESTClient
from massive.exceptions import BadResponse
from massive.rest.models import GroupedDailyAgg, SnapshotMarketType, TickerSnapshot

from .cache import PriceCache
from .interface import MarketDataSource, normalize_ticker

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
        snapshot access (free Basic); polled hourly, or every EOD_RETRY_INTERVAL
        while any tracked ticker has no price yet (failed poll, newly added ticker)
    """

    EOD_MIN_INTERVAL = 3600.0
    EOD_RETRY_INTERVAL = 60.0  # one minute also lets the Basic 5 calls/min window reset
    EOD_LOOKBACK_DAYS = 10

    def __init__(
        self,
        api_key: str,
        price_cache: PriceCache,
        poll_interval: float = 15.0,
        request_timeout: float = 10.0,
    ) -> None:
        self._client = RESTClient(
            api_key=api_key, connect_timeout=request_timeout, read_timeout=request_timeout
        )
        # massive 2.2.0 builds this Timeout but never passes it to urllib3, so a
        # stalled connection would block the poller forever. Apply it to new pools.
        self._client.client.connection_pool_kw["timeout"] = self._client.timeout
        self._cache = price_cache
        self._write_lock = threading.Lock()  # remove_ticker vs. in-flight poll writes
        self._interval = poll_interval
        self._tickers: list[str] = []
        self._mode = "snapshot"
        self._task: asyncio.Task | None = None

    async def start(self, tickers: list[str]) -> None:
        self._tickers = list(dict.fromkeys(normalize_ticker(t) for t in tickers))
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
        ticker = normalize_ticker(ticker)
        if ticker not in self._tickers:
            self._tickers.append(ticker)

    async def remove_ticker(self, ticker: str) -> None:
        ticker = normalize_ticker(ticker)
        with self._write_lock:
            self._tickers = [t for t in self._tickers if t != ticker]
            self._cache.remove(ticker)

    def get_tickers(self) -> list[str]:
        return list(self._tickers)

    def _current_interval(self) -> float:
        """Seconds between polls for the current mode and cache state."""
        if self._mode == "snapshot":
            return self._interval
        if any(t not in self._cache for t in self._tickers):
            return self.EOD_RETRY_INTERVAL
        return max(self._interval, self.EOD_MIN_INTERVAL)

    async def _poll_loop(self) -> None:
        """Poll forever. The first poll already happened in start().

        Wakes every min(poll interval, EOD_RETRY_INTERVAL) and polls once the
        current interval has elapsed, so a ticker added during a long EOD wait
        is fetched on the next short cycle.
        """
        loop = asyncio.get_running_loop()
        last_poll = loop.time()
        while True:
            await asyncio.sleep(min(self._interval, self.EOD_RETRY_INTERVAL))
            if loop.time() - last_poll >= self._current_interval():
                await self._poll_once()
                last_poll = loop.time()

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
                logger.warning(
                    "Massive plan has no snapshot access; switching to end-of-day prices"
                )
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
            self._write(
                snap.ticker,
                price,
                timestamp=snap.updated / 1e9 if snap.updated else None,
                prev_close=snap.prev_day.close if snap.prev_day else None,
            )

    def _poll_eod(self) -> None:
        """Latest two daily closes from grouped-daily (walks back over non-trading days)."""
        wanted = set(self._tickers)
        days: list[dict[str, GroupedDailyAgg]] = []
        today = datetime.now(ZoneInfo("America/New_York")).date()
        day = today
        while len(days) < 2 and day > today - timedelta(days=self.EOD_LOOKBACK_DAYS):
            bars = self._client.get_grouped_daily_aggs(day.isoformat())
            if bars:
                days.append({b.ticker: b for b in bars if b.ticker in wanted})
            day -= timedelta(days=1)
        latest, prior = (days + [{}, {}])[:2]
        for ticker, bar in latest.items():
            prev = prior.get(ticker)
            self._write(
                ticker,
                bar.close,
                timestamp=bar.timestamp / 1000 if bar.timestamp else None,
                prev_close=prev.close if prev else None,
            )

    def _write(
        self, ticker: str, price: float, timestamp: float | None, prev_close: float | None
    ) -> None:
        """Write a polled price, unless the ticker was removed while the poll ran."""
        with self._write_lock:
            if ticker in self._tickers:
                self._cache.update(ticker, price, timestamp=timestamp, prev_close=prev_close)
