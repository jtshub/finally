"""SSE streaming endpoint for live price updates."""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncGenerator

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from .cache import PriceCache

logger = logging.getLogger(__name__)


def create_stream_router(price_cache: PriceCache) -> APIRouter:
    """Create the SSE streaming router with a reference to the price cache.

    This factory pattern lets us inject the PriceCache without globals.
    """
    router = APIRouter(prefix="/api/stream", tags=["streaming"])

    @router.get("/prices")
    async def stream_prices(request: Request) -> StreamingResponse:
        """SSE endpoint for live price updates.

        Streams all tracked ticker prices every ~500ms. The client connects
        with EventSource and receives events in the format:

            data: {"AAPL": {"ticker": "AAPL", "price": 190.50, ...}, ...}

        Includes a retry directive so the browser auto-reconnects on
        disconnection (EventSource built-in behavior).
        """
        return StreamingResponse(
            _generate_events(price_cache, request),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",  # Disable nginx buffering if proxied
            },
        )

    return router


async def _generate_events(
    price_cache: PriceCache,
    request: Request,
    interval: float = 0.5,
    keepalive: float = 15.0,
) -> AsyncGenerator[str, None]:
    """Yield SSE events: a retry directive, then the full price snapshot on every change.

    The cache is checked every `interval` seconds and a snapshot is sent whenever its
    version changes (updates and removals; an emptied cache sends `{}`). A `: ping`
    comment is sent after `keepalive` idle seconds so proxies keep the stream open.
    Stops when the client disconnects.
    """
    yield "retry: 1000\n\n"

    loop = asyncio.get_running_loop()
    last_version = 0  # version 0 means the cache has never been written
    last_sent = loop.time()
    client_ip = request.client.host if request.client else "unknown"
    logger.info("SSE client connected: %s", client_ip)

    try:
        while not await request.is_disconnected():
            version = price_cache.version
            if version != last_version:
                last_version = version
                data = {t: u.to_dict() for t, u in price_cache.get_all().items()}
                yield f"data: {json.dumps(data)}\n\n"
                last_sent = loop.time()
            elif loop.time() - last_sent >= keepalive:
                yield ": ping\n\n"
                last_sent = loop.time()
            await asyncio.sleep(interval)
    finally:
        logger.info("SSE client disconnected: %s", client_ip)
