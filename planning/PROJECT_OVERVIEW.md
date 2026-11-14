# Backend — Developer Guide

## Project Setup

```bash
cd backend
uv sync   # Installs runtime deps plus the dev group (pytest, ruff, rich for the demo)
```

## Market Data API

The market data subsystem lives in `app/market/`. Use these imports:

```python
from app.market import PriceCache, PriceUpdate, MarketDataSource, create_market_data_source, normalize_ticker
```

### Core Types

- **`PriceUpdate`** — Immutable dataclass: `ticker`, `price`, `previous_price`, `timestamp`, `prev_close`, plus properties `change`, `change_percent`, `direction` ("up"/"down"/"flat"), `day_change_percent` (vs `prev_close`, or None), and `to_dict()` for JSON serialization.
  - Tick change (`previous_price`, `direction`) drives the flash animation; daily change (`prev_close`, `day_change_percent`) drives the watchlist "daily change %" column.

- **`PriceCache`** — Thread-safe in-memory store. Key methods:
  - `update(ticker, price, timestamp=None, prev_close=None) -> PriceUpdate` (`prev_close=None` keeps the existing value)
  - `get(ticker) -> PriceUpdate | None`
  - `get_price(ticker) -> float | None`
  - `get_all() -> dict[str, PriceUpdate]`
  - `remove(ticker)`
  - `version` property — monotonic counter, increments on every update and on removal of a cached ticker (for SSE change detection)

- **`MarketDataSource`** — Abstract interface implemented by `SimulatorDataSource` and `MassiveDataSource`. Lifecycle: `start(tickers)` -> `add_ticker()` / `remove_ticker()` -> `stop()`. Both sources normalise tickers with `normalize_ticker()` (strip + upper-case), so `" aapl"` and `"AAPL"` are the same ticker.

- **`create_market_data_source(cache)`** — Factory. Returns `MassiveDataSource` if `MASSIVE_API_KEY` is set (polling every `MASSIVE_POLL_INTERVAL` seconds, default 15), otherwise `SimulatorDataSource`.

### Source behaviour

| | Simulator | Massive |
|---|---|---|
| `prev_close` | Seed price | `prevDay.c` from snapshot |
| `add_ticker()` | Price available immediately | Price appears on next poll (within 1 min in EOD mode) |
| Unknown ticker | Seed derived from the ticker name ($50–$300, same after restart) | Never appears in cache (Massive returns nothing) |
| Free (Basic) key | — | Snapshot 403 `NOT_AUTHORIZED` → auto-switches to US/Eastern end-of-day closes, polled hourly; every minute while any tracked ticker has no price |
| HTTP timeout | — | 10 s per request (`request_timeout`), applied by us because massive 2.2.0 ignores its own |

Callers must tolerate `cache.get_price(t) is None` briefly after `add_ticker()` in Massive mode.

### SSE Streaming

```python
from app.market import create_stream_router

router = create_stream_router(price_cache)  # Returns FastAPI APIRouter
# Endpoint: GET /api/stream/prices (text/event-stream)
```

Each `data:` event is the full `{ticker: PriceUpdate.to_dict()}` snapshot, sent whenever the cache changes (checked every 500 ms). Treat it as the complete state: a removed ticker is simply absent, and removing the last one sends `{}`. When idle, a `: ping` comment is sent every 15 s.

### Seed Data

Default tickers: AAPL, GOOGL, MSFT, AMZN, TSLA, NVDA, META, JPM, V, NFLX. Seed prices and per-ticker volatility/drift params are in `app/market/seed_prices.py`.

## Running Tests

```bash
uv run pytest -v                    # All tests
uv run pytest --cov=app             # With coverage
uv run ruff check app/ tests/       # Lint
uv run ruff format app/ tests/      # Format
```

## Demo

```bash
uv run market_data_demo.py   # Live terminal dashboard with simulated prices
```
