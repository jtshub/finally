"""Tests for MassiveDataSource using real SDK models built from documented JSON."""

from datetime import date
from unittest.mock import MagicMock

import pytest
from massive.exceptions import BadResponse
from massive.rest.models import GroupedDailyAgg, TickerSnapshot

from app.market.cache import PriceCache
from app.market.massive_client import MassiveDataSource, snapshot_price

UPDATED_NS = 1605195918306274000


def _snap(ticker: str, **fields) -> TickerSnapshot:
    """Build a TickerSnapshot from Massive JSON keys (e.g. lastTrade, prevDay)."""
    return TickerSnapshot.from_dict({"ticker": ticker, **fields})


def _full_snap(ticker: str, price: float, prev_close: float) -> TickerSnapshot:
    """Developer+ plan snapshot with lastTrade."""
    return _snap(
        ticker,
        updated=UPDATED_NS,
        day={"c": price - 1},
        prevDay={"c": prev_close},
        min={"c": price - 0.5, "t": 1605195900000},
        lastTrade={"p": price, "t": UPDATED_NS},
    )


def _bar(ticker: str, close: float, ts_ms: int = 1673298000000) -> GroupedDailyAgg:
    return GroupedDailyAgg.from_dict({"T": ticker, "c": close, "t": ts_ms})


def _source(tickers: list[str], poll_interval: float = 60.0) -> tuple[MassiveDataSource, PriceCache]:
    """A source with a mocked REST client and the given tickers."""
    cache = PriceCache()
    source = MassiveDataSource(api_key="test-key", price_cache=cache, poll_interval=poll_interval)
    source._client = MagicMock()
    source._tickers = list(tickers)
    return source, cache


class TestSnapshotPrice:
    """Price fallback chain across plan tiers."""

    def test_prefers_last_trade(self):
        assert snapshot_price(_full_snap("AAPL", 120.47, 119.49)) == 120.47

    def test_falls_back_to_minute_bar(self):
        """Starter plan: no lastTrade."""
        snap = _snap("AAPL", min={"c": 120.3}, day={"c": 120.0}, prevDay={"c": 119.0})
        assert snapshot_price(snap) == 120.3

    def test_falls_back_to_day_close(self):
        snap = _snap("AAPL", day={"c": 120.0}, prevDay={"c": 119.0})
        assert snapshot_price(snap) == 120.0

    def test_falls_back_to_prev_day_close(self):
        """Early morning: snapshot cleared, only prevDay populated."""
        snap = _snap("AAPL", day={"c": 0}, prevDay={"c": 119.0})
        assert snapshot_price(snap) == 119.0

    def test_none_when_empty(self):
        assert snapshot_price(_snap("AAPL")) is None


@pytest.mark.asyncio
class TestSnapshotMode:
    """Polling the full market snapshot endpoint."""

    async def test_poll_updates_cache(self):
        source, cache = _source(["AAPL", "GOOGL"])
        source._client.get_snapshot_all.return_value = [
            _full_snap("AAPL", 190.50, 189.0),
            _full_snap("GOOGL", 175.25, 170.0),
        ]
        await source._poll_once()
        assert cache.get_price("AAPL") == 190.50
        assert cache.get_price("GOOGL") == 175.25

    async def test_requests_tracked_tickers(self):
        source, _ = _source(["AAPL", "MSFT"])
        source._client.get_snapshot_all.return_value = []
        await source._poll_once()
        assert source._client.get_snapshot_all.call_args.kwargs["tickers"] == ["AAPL", "MSFT"]

    async def test_timestamp_nanoseconds_to_seconds(self):
        source, cache = _source(["AAPL"])
        source._client.get_snapshot_all.return_value = [_full_snap("AAPL", 190.5, 189.0)]
        await source._poll_once()
        assert cache.get("AAPL").timestamp == pytest.approx(1605195918.306274)

    async def test_missing_updated_uses_now(self):
        source, cache = _source(["AAPL"])
        source._client.get_snapshot_all.return_value = [_snap("AAPL", day={"c": 120.0})]
        await source._poll_once()
        assert cache.get("AAPL").timestamp > 1_700_000_000

    async def test_prev_close_from_prev_day(self):
        source, cache = _source(["AAPL"])
        source._client.get_snapshot_all.return_value = [_full_snap("AAPL", 110.0, 100.0)]
        await source._poll_once()
        update = cache.get("AAPL")
        assert update.prev_close == 100.0
        assert update.day_change_percent == 10.0

    async def test_starter_plan_snapshot(self):
        """Without lastTrade the minute bar close is used."""
        source, cache = _source(["AAPL"])
        source._client.get_snapshot_all.return_value = [
            _snap("AAPL", updated=UPDATED_NS, min={"c": 120.3}, prevDay={"c": 119.0})
        ]
        await source._poll_once()
        assert cache.get_price("AAPL") == 120.3

    async def test_priceless_snapshot_skipped(self):
        source, cache = _source(["AAPL", "BAD"])
        source._client.get_snapshot_all.return_value = [
            _full_snap("AAPL", 190.5, 189.0),
            _snap("BAD"),
        ]
        await source._poll_once()
        assert cache.get_price("AAPL") == 190.5
        assert cache.get("BAD") is None

    async def test_api_error_does_not_crash(self):
        source, cache = _source(["AAPL"])
        source._client.get_snapshot_all.side_effect = Exception("network error")
        await source._poll_once()
        assert cache.get("AAPL") is None
        assert source._mode == "snapshot"

    async def test_other_bad_response_stays_in_snapshot_mode(self):
        """Rate limits and bad keys are logged, not treated as a plan downgrade."""
        source, _ = _source(["AAPL"])
        source._client.get_snapshot_all.side_effect = BadResponse('{"status":"ERROR"}')
        await source._poll_once()
        assert source._mode == "snapshot"
        source._client.get_grouped_daily_aggs.assert_not_called()

    async def test_empty_tickers_skips_poll(self):
        source, _ = _source([])
        await source._poll_once()
        source._client.get_snapshot_all.assert_not_called()


@pytest.mark.asyncio
class TestEodMode:
    """Fallback to grouped daily closes for plans without snapshot access."""

    async def test_not_authorized_switches_to_eod(self):
        source, cache = _source(["AAPL"])
        source._client.get_snapshot_all.side_effect = BadResponse(
            '{"status":"NOT_AUTHORIZED","message":"You are not entitled to this data."}'
        )
        source._client.get_grouped_daily_aggs.side_effect = [
            [_bar("AAPL", 110.0)],
            [_bar("AAPL", 100.0)],
        ]
        await source._poll_once()
        assert source._mode == "eod"
        assert cache.get_price("AAPL") == 110.0
        assert cache.get("AAPL").prev_close == 100.0

    async def test_eod_walks_back_over_empty_days(self):
        source, cache = _source(["AAPL"])
        source._mode = "eod"
        source._client.get_grouped_daily_aggs.side_effect = [
            [],
            [_bar("AAPL", 110.0)],
            [],
            [_bar("AAPL", 100.0)],
        ]
        await source._poll_once()
        days = [c.args[0] for c in source._client.get_grouped_daily_aggs.call_args_list]
        assert len(days) == 4
        assert days[0] == date.today().isoformat()
        assert cache.get_price("AAPL") == 110.0
        assert cache.get("AAPL").prev_close == 100.0

    async def test_eod_filters_to_tracked_tickers(self):
        source, cache = _source(["AAPL"])
        source._mode = "eod"
        source._client.get_grouped_daily_aggs.return_value = [_bar("AAPL", 110.0), _bar("IBM", 5.0)]
        await source._poll_once()
        assert cache.get_price("AAPL") == 110.0
        assert cache.get("IBM") is None

    async def test_eod_timestamp_milliseconds_to_seconds(self):
        source, cache = _source(["AAPL"])
        source._mode = "eod"
        source._client.get_grouped_daily_aggs.return_value = [_bar("AAPL", 110.0)]
        await source._poll_once()
        assert cache.get("AAPL").timestamp == 1673298000.0

    async def test_eod_gives_up_after_lookback(self):
        source, cache = _source(["AAPL"])
        source._mode = "eod"
        source._client.get_grouped_daily_aggs.return_value = []
        await source._poll_once()
        calls = source._client.get_grouped_daily_aggs.call_count
        assert calls == MassiveDataSource.EOD_LOOKBACK_DAYS
        assert cache.get("AAPL") is None

    async def test_eod_interval_is_at_least_an_hour(self):
        source, _ = _source(["AAPL"], poll_interval=15.0)
        assert source._current_interval() == 15.0
        source._mode = "eod"
        assert source._current_interval() == 3600.0


@pytest.mark.asyncio
class TestLifecycle:
    """Ticker management and start/stop."""

    async def test_add_ticker_normalizes(self):
        source, _ = _source([])
        await source.add_ticker("  aapl ")
        await source.add_ticker("AAPL")
        assert source.get_tickers() == ["AAPL"]

    async def test_remove_ticker(self):
        source, cache = _source(["AAPL", "GOOGL"])
        cache.update("AAPL", 190.00)
        await source.remove_ticker("aapl")
        assert source.get_tickers() == ["GOOGL"]
        assert cache.get("AAPL") is None

    async def test_get_tickers_returns_copy(self):
        source, _ = _source(["AAPL"])
        source.get_tickers().append("X")
        assert source.get_tickers() == ["AAPL"]

    async def test_start_polls_immediately_and_runs_loop(self):
        source, cache = _source([])
        source._client.get_snapshot_all.return_value = [_full_snap("AAPL", 190.5, 189.0)]
        await source.start(["aapl"])
        assert source.get_tickers() == ["AAPL"]
        assert cache.get_price("AAPL") == 190.5
        assert source._task is not None and not source._task.done()
        await source.stop()
        assert source._task is None

    async def test_stop_is_idempotent(self):
        source, _ = _source([])
        await source.stop()
        await source.stop()
