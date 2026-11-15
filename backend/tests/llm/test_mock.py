"""Tests for LLM_MOCK deterministic responses."""

import pytest

from app.llm import LLMResponse, TradeAction, WatchlistChange, get_llm_response
from app.llm.mock import DEFAULT_MESSAGE, mock_response


def test_buy():
    r = mock_response("buy 5 AAPL")
    assert r.message == "Buying 5 AAPL."
    assert r.trades == [TradeAction(ticker="AAPL", side="buy", quantity=5)]
    assert r.watchlist_changes == []


def test_buy_reverse_order_and_case():
    r = mock_response("Please Buy aapl 2.5")
    assert r.trades == [TradeAction(ticker="AAPL", side="buy", quantity=2.5)]
    assert r.message == "Buying 2.5 AAPL."


def test_sell():
    r = mock_response("sell 3 TSLA")
    assert r.message == "Selling 3 TSLA."
    assert r.trades == [TradeAction(ticker="TSLA", side="sell", quantity=3)]


def test_watch():
    r = mock_response("watch PYPL")
    assert r.watchlist_changes == [WatchlistChange(ticker="PYPL", action="add")]
    assert r.trades == []


def test_unwatch():
    r = mock_response("unwatch nflx")
    assert r.watchlist_changes == [WatchlistChange(ticker="NFLX", action="remove")]


@pytest.mark.parametrize("msg", ["hello", "how is my portfolio?", "buy something", "my watchlist"])
def test_default(msg):
    assert mock_response(msg) == LLMResponse(message=DEFAULT_MESSAGE)


def test_get_llm_response_uses_mock(monkeypatch):
    monkeypatch.setenv("LLM_MOCK", "true")

    def boom(**kwargs):
        raise AssertionError("network call in mock mode")

    monkeypatch.setattr("app.llm.client.completion", boom)
    r = get_llm_response({}, [], "buy 5 AAPL")
    assert r.trades[0].ticker == "AAPL"
