"""Tests for the snapshot loop and chat action execution."""

import asyncio

import pytest

from app import db
from app.llm import LLMResponse, TradeAction, WatchlistChange
from app.market import PriceCache
from app.services import chat, portfolio


class FakeSource:
    """Records add/remove calls and seeds the cache like the simulator."""

    def __init__(self, cache):
        self.cache = cache
        self.removed = []

    async def add_ticker(self, ticker):
        self.cache.update(ticker, 50.0)

    async def remove_ticker(self, ticker):
        self.removed.append(ticker)
        self.cache.remove(ticker)


@pytest.fixture
def cache(tmp_path):
    db.init_db(str(tmp_path / "t.db"))
    c = PriceCache()
    c.update("AAPL", 100.0)
    return c


async def test_snapshot_loop_records(cache):
    task = asyncio.create_task(portfolio.snapshot_loop(cache, interval=0.01))
    await asyncio.sleep(0.05)
    task.cancel()
    snaps = db.get_snapshots()
    assert len(snaps) >= 2
    assert snaps[0]["total_value"] == 10000.0


async def test_execute_actions_adds_then_trades(cache):
    response = LLMResponse(
        message="ok",
        watchlist_changes=[WatchlistChange(ticker="PYPL", action="add")],
        trades=[
            TradeAction(ticker="PYPL", side="buy", quantity=2),
            TradeAction(ticker="AAPL", side="buy", quantity=1000),
        ],
    )
    result = await chat.execute_actions(cache, FakeSource(cache), response)
    assert result["watchlist_changes"][0]["status"] == "executed"
    assert result["trades"][0] == {
        "ticker": "PYPL",
        "side": "buy",
        "quantity": 2,
        "status": "executed",
        "price": 50.0,
        "error": None,
    }
    assert result["trades"][1]["status"] == "failed"
    assert db.get_cash() == 9900.0


async def test_remove_unknown_ticker_fails(cache):
    response = LLMResponse(
        message="ok", watchlist_changes=[WatchlistChange(ticker="ZZZ", action="remove")]
    )
    result = await chat.execute_actions(cache, FakeSource(cache), response)
    assert result["watchlist_changes"][0]["status"] == "failed"
