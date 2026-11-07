"""Factory for creating market data sources."""

from __future__ import annotations

import logging
import os

from .cache import PriceCache
from .interface import MarketDataSource
from .massive_client import MassiveDataSource
from .simulator import SimulatorDataSource

logger = logging.getLogger(__name__)


def create_market_data_source(price_cache: PriceCache) -> MarketDataSource:
    """Create the market data source selected by environment variables.

    - MASSIVE_API_KEY set and non-empty → MassiveDataSource, polling every
      MASSIVE_POLL_INTERVAL seconds (default 15)
    - Otherwise → SimulatorDataSource (GBM simulation)

    Returns an unstarted source. Caller must await source.start(tickers).
    """
    api_key = os.environ.get("MASSIVE_API_KEY", "").strip()
    if api_key:
        interval = float(os.environ.get("MASSIVE_POLL_INTERVAL", "15"))
        logger.info("Market data source: Massive API (every %.1fs)", interval)
        return MassiveDataSource(api_key, price_cache, poll_interval=interval)
    logger.info("Market data source: GBM Simulator")
    return SimulatorDataSource(price_cache)
