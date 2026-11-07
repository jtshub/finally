"""Tests for the SSE price stream."""

import json

import pytest

from app.market.cache import PriceCache
from app.market.stream import _generate_events, create_stream_router


class FakeRequest:
    """Request stub that reports disconnect after `polls` checks."""

    client = None

    def __init__(self, polls: int) -> None:
        self._polls = polls

    async def is_disconnected(self) -> bool:
        self._polls -= 1
        return self._polls < 0


async def _collect(cache: PriceCache, polls: int) -> list[str]:
    return [e async for e in _generate_events(cache, FakeRequest(polls), interval=0.01)]


def _payloads(events: list[str]) -> list[dict]:
    return [json.loads(e.removeprefix("data: ")) for e in events if e.startswith("data: ")]


def test_router_has_prices_route():
    router = create_stream_router(PriceCache())
    assert [r.path for r in router.routes] == ["/api/stream/prices"]


def test_routers_are_independent():
    """Each call builds a fresh router (no duplicate routes)."""
    create_stream_router(PriceCache())
    router = create_stream_router(PriceCache())
    assert len(router.routes) == 1


@pytest.mark.asyncio
async def test_first_event_is_retry_directive():
    events = await _collect(PriceCache(), polls=0)
    assert events == ["retry: 1000\n\n"]


@pytest.mark.asyncio
async def test_sends_all_prices():
    cache = PriceCache()
    cache.update("AAPL", 190.0, prev_close=180.0)
    cache.update("MSFT", 420.0)
    [payload] = _payloads(await _collect(cache, polls=1))
    assert set(payload) == {"AAPL", "MSFT"}
    assert payload["AAPL"]["price"] == 190.0
    assert payload["AAPL"]["prev_close"] == 180.0


@pytest.mark.asyncio
async def test_event_format():
    cache = PriceCache()
    cache.update("AAPL", 190.0)
    events = await _collect(cache, polls=1)
    assert events[1].startswith("data: ") and events[1].endswith("\n\n")


@pytest.mark.asyncio
async def test_unchanged_version_not_resent():
    cache = PriceCache()
    cache.update("AAPL", 190.0)
    assert len(_payloads(await _collect(cache, polls=5))) == 1


@pytest.mark.asyncio
async def test_empty_cache_sends_nothing():
    assert _payloads(await _collect(PriceCache(), polls=3)) == []
