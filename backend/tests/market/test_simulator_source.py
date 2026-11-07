"""Integration tests for SimulatorDataSource."""

import asyncio

from app.market.cache import PriceCache
from app.market.simulator import SimulatorDataSource
from tests.helpers import wait_until


class TestSimulatorDataSource:
    """Integration tests for the SimulatorDataSource."""

    async def test_start_populates_cache(self):
        """Test that start() immediately populates the cache."""
        cache = PriceCache()
        source = SimulatorDataSource(price_cache=cache, update_interval=0.1)
        await source.start(["AAPL", "GOOGL"])

        # Cache should have seed prices immediately (before first loop tick)
        assert cache.get("AAPL") is not None
        assert cache.get("GOOGL") is not None

        await source.stop()

    async def test_prices_update_over_time(self):
        """The background loop keeps writing new prices."""
        cache = PriceCache()
        source = SimulatorDataSource(price_cache=cache, update_interval=0.01)
        await source.start(["AAPL"])
        initial_version = cache.version
        await wait_until(lambda: cache.version >= initial_version + 3)
        await source.stop()

    async def test_stop_is_clean(self):
        """Test that stop() is clean and idempotent."""
        cache = PriceCache()
        source = SimulatorDataSource(price_cache=cache, update_interval=0.1)
        await source.start(["AAPL"])
        await source.stop()
        # Double stop should not raise
        await source.stop()

    async def test_add_ticker(self):
        """Test adding a ticker dynamically."""
        cache = PriceCache()
        source = SimulatorDataSource(price_cache=cache, update_interval=0.1)
        await source.start(["AAPL"])

        await source.add_ticker("TSLA")
        assert "TSLA" in source.get_tickers()
        assert cache.get("TSLA") is not None

        await source.stop()

    async def test_remove_ticker(self):
        """Test removing a ticker."""
        cache = PriceCache()
        source = SimulatorDataSource(price_cache=cache, update_interval=0.1)
        await source.start(["AAPL", "TSLA"])

        await source.remove_ticker("TSLA")
        assert "TSLA" not in source.get_tickers()
        assert cache.get("TSLA") is None

        await source.stop()

    async def test_get_tickers(self):
        """Test getting the list of active tickers."""
        cache = PriceCache()
        source = SimulatorDataSource(price_cache=cache, update_interval=0.1)
        await source.start(["AAPL", "GOOGL"])

        tickers = source.get_tickers()
        assert set(tickers) == {"AAPL", "GOOGL"}

        await source.stop()

    async def test_empty_start(self):
        """Test starting with no tickers."""
        cache = PriceCache()
        source = SimulatorDataSource(price_cache=cache, update_interval=0.1)
        await source.start([])

        assert len(cache) == 0
        assert source.get_tickers() == []

        await source.stop()

    async def test_exception_resilience(self):
        """A failing step is logged and the loop keeps producing prices."""
        cache = PriceCache()
        source = SimulatorDataSource(price_cache=cache, update_interval=0.01)
        await source.start(["AAPL"])
        real_step = source._sim.step
        calls = {"n": 0}

        def flaky_step():
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("boom")
            return real_step()

        source._sim.step = flaky_step
        version = cache.version
        await wait_until(lambda: calls["n"] >= 2 and cache.version > version)
        assert not source._task.done()
        await source.stop()

    async def test_custom_update_interval(self):
        """A short interval produces frequent updates; a long one produces none quickly."""
        cache = PriceCache()
        fast = SimulatorDataSource(price_cache=cache, update_interval=0.01)
        await fast.start(["AAPL"])
        version = cache.version
        await wait_until(lambda: cache.version > version + 2)
        await fast.stop()

        slow_cache = PriceCache()
        slow = SimulatorDataSource(price_cache=slow_cache, update_interval=10.0)
        await slow.start(["AAPL"])
        await asyncio.sleep(0.05)
        assert slow_cache.version == 2  # seed write + the loop's immediate first step
        await slow.stop()

    async def test_custom_event_probability(self):
        """event_probability=1.0 shocks every tick by 2-5% on top of a tiny GBM move."""
        cache = PriceCache()
        source = SimulatorDataSource(price_cache=cache, update_interval=0.01, event_probability=1.0)
        await source.start(["AAPL"])
        await wait_until(lambda: cache.get("AAPL").previous_price != 190.0)
        update = cache.get("AAPL")
        assert 1.9 <= abs(update.change_percent) <= 5.1
        await source.stop()

    async def test_seed_price_is_prev_close(self):
        """Cache is seeded with the seed price as prev_close, kept across ticks."""
        cache = PriceCache()
        source = SimulatorDataSource(price_cache=cache, update_interval=0.05)
        await source.start(["AAPL"])
        assert cache.get("AAPL").prev_close == 190.00
        await asyncio.sleep(0.15)
        assert cache.get("AAPL").prev_close == 190.00
        assert cache.get("AAPL").day_change_percent is not None
        await source.stop()

    async def test_added_ticker_has_prev_close(self):
        """A ticker added at runtime has its seed as prev_close."""
        cache = PriceCache()
        source = SimulatorDataSource(price_cache=cache, update_interval=10.0)
        await source.start(["AAPL"])
        await source.add_ticker("PYPL")
        update = cache.get("PYPL")
        assert update.prev_close == update.price
        await source.stop()

    async def test_add_existing_ticker_keeps_price(self):
        """Re-adding a tracked ticker does not reset its cached price."""
        cache = PriceCache()
        source = SimulatorDataSource(price_cache=cache, update_interval=10.0)
        await source.start(["AAPL"])
        cache.update("AAPL", 999.0)
        await source.add_ticker("AAPL")
        assert cache.get_price("AAPL") == 999.0
        await source.stop()


async def test_tickers_are_normalized():
    """Lower-case or padded tickers map to the same upper-case ticker."""
    cache = PriceCache()
    source = SimulatorDataSource(price_cache=cache, update_interval=10.0)
    await source.start(["aapl "])
    await source.add_ticker(" AAPL")
    await source.add_ticker("tsla")
    assert source.get_tickers() == ["AAPL", "TSLA"]
    await source.remove_ticker(" tsla ")
    assert source.get_tickers() == ["AAPL"]
    assert "TSLA" not in cache
    await source.stop()
