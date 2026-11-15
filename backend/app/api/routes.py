"""REST routers: health, portfolio, watchlist, chat."""

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app import db
from app.services import chat, portfolio, watchlist

router = APIRouter(prefix="/api")


class TradeRequest(BaseModel):
    ticker: str
    quantity: float
    side: str


class TickerRequest(BaseModel):
    ticker: str


class ChatRequest(BaseModel):
    message: str


@router.get("/health")
def health() -> dict:
    """Liveness check."""
    return {"status": "ok"}


@router.get("/portfolio")
def get_portfolio(request: Request) -> dict:
    """Cash, positions and totals at live prices."""
    return portfolio.get_portfolio(request.app.state.cache)


@router.post("/portfolio/trade")
def trade(body: TradeRequest, request: Request) -> dict:
    """Execute a market order; 400 on validation failure."""
    cache = request.app.state.cache
    try:
        result = portfolio.execute_trade(cache, body.ticker, body.side, body.quantity)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"trade": result, "portfolio": portfolio.get_portfolio(cache)}


@router.get("/portfolio/history")
def history() -> list[dict]:
    """Portfolio value snapshots, oldest first."""
    return portfolio.get_history()


@router.get("/watchlist")
def get_watchlist(request: Request) -> list[dict]:
    """Watchlist with latest prices."""
    return watchlist.get_watchlist(request.app.state.cache)


@router.post("/watchlist", status_code=201)
async def add_watchlist(body: TickerRequest, request: Request) -> dict:
    """Add a ticker; 400 if invalid or already present."""
    try:
        ticker = await watchlist.add_ticker(request.app.state.source, body.ticker)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"ticker": ticker}


@router.delete("/watchlist/{ticker}")
async def remove_watchlist(ticker: str, request: Request) -> dict:
    """Remove a ticker; 404 if absent."""
    try:
        ticker = await watchlist.remove_ticker(request.app.state.source, ticker)
    except watchlist.NotInWatchlistError as e:
        raise HTTPException(404, str(e))
    return {"ticker": ticker}


@router.post("/chat")
async def post_chat(body: ChatRequest, request: Request) -> dict:
    """One chat turn with auto-executed actions."""
    if not body.message.strip():
        raise HTTPException(400, "Message must not be empty")
    state = request.app.state
    return await chat.handle_chat(state.cache, state.source, body.message)


@router.get("/chat/history")
def chat_history() -> list[dict]:
    """Stored chat messages, oldest first."""
    return [
        {k: m[k] for k in ("role", "content", "actions", "created_at")}
        for m in db.get_chat_messages(limit=100)
    ]
