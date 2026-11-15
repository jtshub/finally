"""FinAlly FastAPI application: API, SSE stream, background tasks, static frontend."""

import asyncio
import os
from contextlib import asynccontextmanager, suppress
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app import db
from app.api.routes import router
from app.market import PriceCache, create_market_data_source, create_stream_router
from app.services.portfolio import snapshot_loop

BACKEND_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BACKEND_DIR.parent / ".env")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Init DB, start market source on watchlist + held tickers, run the snapshot loop."""
    db.init_db(os.environ.get("FINALLY_DB_PATH"))
    cache = app.state.cache
    source = create_market_data_source(cache)
    tickers = db.get_watchlist() + [p["ticker"] for p in db.get_positions()]
    await source.start(list(dict.fromkeys(tickers)))
    app.state.source = source
    snapshots = asyncio.create_task(snapshot_loop(cache))
    yield
    snapshots.cancel()
    with suppress(asyncio.CancelledError):
        await snapshots
    await source.stop()


def create_app() -> FastAPI:
    """Build the app; static files are mounted last, only if STATIC_DIR exists."""
    app = FastAPI(title="FinAlly", lifespan=lifespan)
    app.state.cache = PriceCache()
    app.include_router(router)
    app.include_router(create_stream_router(app.state.cache))
    static_dir = Path(os.environ.get("STATIC_DIR", BACKEND_DIR / "static"))
    if static_dir.is_dir():
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
    return app


app = create_app()
