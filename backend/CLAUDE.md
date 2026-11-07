# Backend — Developer Guide

## Project Setup

```bash
cd backend
uv sync --extra dev   # Install all dependencies including test/lint tools
```

## Market Data API

The market data subsystem lives in `app/market/`. Use these imports:

```python
from app.market import PriceCache, PriceUpdate, MarketDataSource, create_market_data_source
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
  - `version` property — monotonic counter, increments on every update (for SSE change detection)

- **`MarketDataSource`** — Abstract interface implemented by `SimulatorDataSource` and `MassiveDataSource`. Lifecycle: `start(tickers)` -> `add_ticker()` / `remove_ticker()` -> `stop()`.

- **`create_market_data_source(cache)`** — Factory. Returns `MassiveDataSource` if `MASSIVE_API_KEY` is set (polling every `MASSIVE_POLL_INTERVAL` seconds, default 15), otherwise `SimulatorDataSource`.

### Source behaviour

| | Simulator | Massive |
|---|---|---|
| `prev_close` | Seed price | `prevDay.c` from snapshot |
| `add_ticker()` | Price available immediately | Price appears on next poll |
| Free (Basic) key | — | Snapshot 403 `NOT_AUTHORIZED` → auto-switches to end-of-day closes, polled hourly |

Callers must tolerate `cache.get_price(t) is None` briefly after `add_ticker()` in Massive mode.

### SSE Streaming

```python
from app.market import create_stream_router

router = create_stream_router(price_cache)  # Returns FastAPI APIRouter
# Endpoint: GET /api/stream/prices (text/event-stream)
```

### Seed Data

Default tickers: AAPL, GOOGL, MSFT, AMZN, TSLA, NVDA, META, JPM, V, NFLX. Seed prices and per-ticker volatility/drift params are in `app/market/seed_prices.py`.

## Running Tests

```bash
uv run --extra dev pytest -v              # All tests
uv run --extra dev pytest --cov=app       # With coverage
uv run --extra dev ruff check app/ tests/ # Lint
```

## Demo

```bash
uv run market_data_demo.py   # Live terminal dashboard with simulated prices
```
