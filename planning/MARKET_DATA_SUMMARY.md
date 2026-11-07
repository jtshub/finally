# Market Data Backend — Summary

**Status:** Complete, tested, reviewed. Updated 2026-11-07 to apply all fixes in `MARKET_INTERFACE.md` §8, then all findings in `MARKET_DATA_REVIEW.md` (second review, same day).

## 2026-11-07 Review Fixes (`MARKET_DATA_REVIEW.md`)

- **Massive timeout (M1)** — massive 2.2.0 ignores its own timeout; a silent server hung the poller forever (reproduced). The source now installs a 10 s timeout on the client's connection pool.
- **No resurrection (M2)** — a ticker removed mid-poll was written back to the cache (reproduced). Writes now happen under a lock, only for still-tracked tickers.
- **EOD retry (M3)** — on free keys, a failed first poll or a newly added ticker is retried after 60 s instead of an hour.
- **Ticker normalisation (M4)** — `normalize_ticker()` (strip + upper-case) is shared by both sources and exported from `app.market`.
- **Stable seeds (L1)** — unknown tickers get a seed derived from the ticker name, the same after a restart.
- **Smaller fixes** — empty `MASSIVE_POLL_INTERVAL` means 15 s, with a 1 s floor (L2). `PriceCache.remove()` bumps `version`, so SSE pushes removals and an emptied cache sends `{}` (L3). SSE sends a `: ping` every 15 s when idle (L4) and no longer swallows `CancelledError` (L5). The EOD date is US/Eastern (L6).
- **Hygiene (L7)** — dev tools and `rich` moved to a uv `[dependency-groups]` dev group (plain `uv run pytest`), the redundant conftest and asyncio markers were removed, and ruff format is clean.
- **Tests (L8)** — seeded GBM volatility/correlation tests, a silent-socket timeout test, removal-race tests, poll-loop scheduling tests, and real exception injection. Timing tests use a bounded `wait_until` helper (`tests/helpers.py`) instead of fixed sleeps.

## 2026-11-07 Revision

- **Massive fixed** — the old code read `last_trade.timestamp` (does not exist; it is `sip_timestamp`), so every snapshot was skipped and the cache never filled. Now uses `snap.updated / 1e9` (ns) and a price fallback chain `lastTrade → min → day → prevDay` (`snapshot_price()`) so Starter plans work.
- **Free keys work** — a snapshot 403 `NOT_AUTHORIZED` switches to `eod` mode (grouped-daily closes, hourly).
- **Daily change %** — `PriceUpdate.prev_close` + `day_change_percent`; Massive uses `prevDay.c`, simulator uses the seed price.
- **`MASSIVE_POLL_INTERVAL`** env var (default 15 s); added `.env.example`.
- **SSE router** is now built per `create_stream_router()` call (was a module-level router that accumulated duplicate routes).
- **Tests** — Massive tests now build real `TickerSnapshot`/`GroupedDailyAgg` models from documented JSON instead of `MagicMock`, so wrong field names fail. New `test_stream.py`.
- Still unverified: the exact 403 body from a real Basic key (see `MARKET_INTERFACE.md` §9).

## What Was Built

A complete market data subsystem in `backend/app/market/` (8 modules, ~500 lines) providing live price simulation and real market data via a unified interface.

### Architecture

```
MarketDataSource (ABC)
├── SimulatorDataSource  →  GBM simulator (default, no API key needed)
└── MassiveDataSource    →  Polygon.io REST poller (when MASSIVE_API_KEY set)
        │
        ▼
   PriceCache (thread-safe, in-memory)
        │
        ├──→ SSE stream endpoint (/api/stream/prices)
        ├──→ Portfolio valuation
        └──→ Trade execution
```

### Modules

| File | Purpose |
|------|---------|
| `models.py` | `PriceUpdate` — immutable frozen dataclass (ticker, price, previous_price, timestamp, change, direction) |
| `interface.py` | `MarketDataSource` — abstract base class defining `start/stop/add_ticker/remove_ticker/get_tickers` |
| `cache.py` | `PriceCache` — thread-safe price store with version counter for SSE change detection |
| `seed_prices.py` | Realistic seed prices, per-ticker GBM params (drift/volatility), correlation groups |
| `simulator.py` | `GBMSimulator` (Geometric Brownian Motion with Cholesky-correlated moves) + `SimulatorDataSource` |
| `massive_client.py` | `MassiveDataSource` — REST polling client for Polygon.io via the `massive` package |
| `factory.py` | `create_market_data_source()` — selects simulator or Massive based on `MASSIVE_API_KEY` env var |
| `stream.py` | `create_stream_router()` — FastAPI SSE endpoint factory using version-based change detection |

### Key Design Decisions

- **Strategy pattern** — both data sources implement the same ABC; downstream code is source-agnostic
- **PriceCache as single point of truth** — producers write, consumers read; no direct coupling
- **GBM with correlated moves** — Cholesky decomposition of sector-based correlation matrix; tech stocks correlate at 0.6, finance at 0.5, cross-sector at 0.3
- **Random shock events** — ~0.1% chance per tick per ticker of a 2-5% move for visual drama
- **SSE over WebSockets** — simpler, one-way push, universal browser support

## Test Suite

**126 tests, all passing; 100% line coverage** (`uv run pytest --cov=app`). 7 test modules in `backend/tests/market/`:

| Module | Tests | Covers |
|--------|-------|--------|
| test_models.py | 14 | `PriceUpdate` maths and serialisation |
| test_cache.py | 19 | `PriceCache` updates, `prev_close`, versioning |
| test_simulator.py | 25 | GBM steps, seeds, correlations, volatility statistics |
| test_simulator_source.py | 14 | Simulator lifecycle, normalisation, error resilience |
| test_factory.py | 11 | Source selection, poll-interval parsing |
| test_massive.py | 33 | Snapshot/EOD parsing from real SDK models, timeout, races, scheduling |
| test_stream.py | 10 | SSE format, change detection, removals, keepalive, route |

## First Code Review (2026-02-10, `archive/MARKET_DATA_REVIEW.md`)

A comprehensive code review identified 7 issues. All were resolved:

1. **pyproject.toml build config** — added `[tool.hatch.build.targets.wheel] packages = ["app"]`
2. **Lazy imports removed** — `massive` is a core dependency; imports moved to top level
3. **SSE return type fixed** — `_generate_events` annotated as `AsyncGenerator[str, None]`
4. **Public `get_tickers()`** — added to `GBMSimulator` to avoid private attribute access
5. **Correlation constants cleaned up** — removed unused `DEFAULT_CORR`, consolidated into `CROSS_GROUP_CORR`
6. **Unused test imports removed** — `pytest`, `math`, `asyncio` cleaned from 4 test files
7. **Massive test mocks fixed** — `source._client` set in tests, patches target correct names

## Demo

A Rich terminal demo is available at `backend/market_data_demo.py`:

```bash
cd backend
uv run market_data_demo.py
```

Displays a live-updating dashboard with all 10 tickers, sparklines, color-coded direction arrows, and an event log for notable price moves. Runs 60 seconds or until Ctrl+C.

## Usage for Downstream Code

```python
from app.market import PriceCache, create_market_data_source

# Startup
cache = PriceCache()
source = create_market_data_source(cache)  # Reads MASSIVE_API_KEY
await source.start(["AAPL", "GOOGL", "MSFT", ...])

# Read prices
update = cache.get("AAPL")          # PriceUpdate or None
price = cache.get_price("AAPL")     # float or None
all_prices = cache.get_all()        # dict[str, PriceUpdate]

# Dynamic watchlist
await source.add_ticker("TSLA")
await source.remove_ticker("GOOGL")

# Shutdown
await source.stop()
```
