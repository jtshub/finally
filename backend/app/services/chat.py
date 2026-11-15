"""Chat orchestration: context -> LLM -> execute actions -> store -> respond."""

import asyncio

from app import db
from app.llm import LLMResponse, get_llm_response
from app.market import MarketDataSource, PriceCache
from app.services import portfolio, watchlist


def build_context(cache: PriceCache) -> dict:
    """Portfolio response plus watchlist tickers with live prices."""
    context = portfolio.get_portfolio(cache)
    context["watchlist"] = [{"ticker": t, "price": cache.get_price(t)} for t in db.get_watchlist()]
    return context


async def handle_chat(cache: PriceCache, source: MarketDataSource, message: str) -> dict:
    """Run one chat turn and return the contract response shape."""
    context = build_context(cache)
    history = db.get_chat_messages()
    response = await asyncio.to_thread(get_llm_response, context, history, message)
    result = await execute_actions(cache, source, response)
    db.add_chat_message("user", message)
    actions = {"trades": result["trades"], "watchlist_changes": result["watchlist_changes"]}
    db.add_chat_message("assistant", result["message"], actions)
    return result


async def execute_actions(
    cache: PriceCache, source: MarketDataSource, response: LLMResponse
) -> dict:
    """Apply watchlist changes, then trades, using the same validation as manual actions."""
    changes = [await _apply_change(source, c.ticker, c.action) for c in response.watchlist_changes]
    trades = [_apply_trade(cache, t.ticker, t.side, t.quantity) for t in response.trades]
    return {"message": response.message, "trades": trades, "watchlist_changes": changes}


async def _apply_change(source: MarketDataSource, ticker: str, action: str) -> dict:
    result = {
        "ticker": ticker.strip().upper(),
        "action": action,
        "status": "executed",
        "error": None,
    }
    try:
        if action == "add":
            await watchlist.add_ticker(source, ticker)
        else:
            await watchlist.remove_ticker(source, ticker)
    except (ValueError, LookupError) as e:
        result.update(status="failed", error=str(e))
    return result


def _apply_trade(cache: PriceCache, ticker: str, side: str, quantity: float) -> dict:
    result = {
        "ticker": ticker.strip().upper(),
        "side": side,
        "quantity": quantity,
        "status": "executed",
        "price": None,
        "error": None,
    }
    try:
        trade = portfolio.execute_trade(cache, ticker, side, quantity)
        result["price"] = trade["price"]
    except ValueError as e:
        result.update(status="failed", error=str(e))
    return result
