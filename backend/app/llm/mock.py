"""Deterministic mock responses for LLM_MOCK=true (E2E tests depend on these rules)."""

import re

from .models import LLMResponse, TradeAction, WatchlistChange

DEFAULT_MESSAGE = "Mock response: I can help with your portfolio."

_TRADE = re.compile(r"\b(buy|sell)\s+(\d+(?:\.\d+)?)\s+([A-Za-z]{1,5})\b", re.IGNORECASE)
_TRADE_REV = re.compile(r"\b(buy|sell)\s+([A-Za-z]{1,5})\s+(\d+(?:\.\d+)?)\b", re.IGNORECASE)
_WATCH = re.compile(r"\b(unwatch|watch)\s+([A-Za-z]{1,5})\b", re.IGNORECASE)


def _fmt(quantity: float) -> str:
    """Format a quantity without a trailing .0 for whole numbers."""
    return f"{quantity:g}"


def _parse_trade(text: str) -> tuple[str, float, str] | None:
    """Extract (side, quantity, ticker) from 'buy 5 AAPL' or 'buy AAPL 5'."""
    if m := _TRADE.search(text):
        return m.group(1).lower(), float(m.group(2)), m.group(3).upper()
    if m := _TRADE_REV.search(text):
        return m.group(1).lower(), float(m.group(3)), m.group(2).upper()
    return None


def mock_response(user_message: str) -> LLMResponse:
    """Return a deterministic response parsed from simple commands in the message."""
    if parsed := _parse_trade(user_message):
        side, qty, ticker = parsed
        verb = "Buying" if side == "buy" else "Selling"
        return LLMResponse(
            message=f"{verb} {_fmt(qty)} {ticker}.",
            trades=[TradeAction(ticker=ticker, side=side, quantity=qty)],
        )
    if m := _WATCH.search(user_message):
        cmd, ticker = m.group(1).lower(), m.group(2).upper()
        action = "add" if cmd == "watch" else "remove"
        verb = "Adding" if action == "add" else "Removing"
        prep = "to" if action == "add" else "from"
        return LLMResponse(
            message=f"{verb} {ticker} {prep} your watchlist.",
            watchlist_changes=[WatchlistChange(ticker=ticker, action=action)],
        )
    return LLMResponse(message=DEFAULT_MESSAGE)
