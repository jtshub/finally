"""Structured output models for the LLM chat assistant."""

from typing import Literal

from pydantic import BaseModel


class TradeAction(BaseModel):
    """A market order the assistant wants executed."""

    ticker: str
    side: Literal["buy", "sell"]
    quantity: float


class WatchlistChange(BaseModel):
    """A watchlist add/remove the assistant wants applied."""

    ticker: str
    action: Literal["add", "remove"]


class LLMResponse(BaseModel):
    """Complete structured response from the assistant."""

    message: str
    trades: list[TradeAction] = []
    watchlist_changes: list[WatchlistChange] = []
