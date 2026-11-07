# Market Data Interface — Unified Python API

How FinAlly gets stock prices. One interface and two implementations: the **Massive API** when
`MASSIVE_API_KEY` is set, otherwise the **simulator**. Everything downstream (SSE, portfolio
valuation, trade execution, LLM context) reads from one shared `PriceCache` and never knows
which source is running.

Code lives in `backend/app/market/`. This document describes that design and, in §8, the
changes the Massive research (`MASSIVE_API.md`) shows are needed.

---

## 1. Architecture

```
            create_market_data_source(cache)        ← reads MASSIVE_API_KEY
                         │
          ┌──────────────┴──────────────┐
  SimulatorDataSource           MassiveDataSource
  (GBM, ticks every 0.5s)       (REST poll, every N s)
          └──────────────┬──────────────┘
                         ▼ cache.update(...)
                    PriceCache  (in-memory, thread-safe, versioned)
                         │ get / get_all / get_price
      ┌──────────────────┼─────────────────────┬──────────────┐
  SSE /api/stream/prices  portfolio valuation   trade fills    LLM context
```

Rules:

1. **Producers write, consumers read.** Only the active data source writes to the cache.
2. **Consumers never call a data source for a price.** They call `cache.get_price(ticker)`.
3. **The data source owns the set of tracked tickers.** Watchlist routes call
   `source.add_ticker()` / `source.remove_ticker()`.

## 2. Module Layout

| File | Contents |
|---|---|
| `models.py` | `PriceUpdate` frozen dataclass |
| `cache.py` | `PriceCache` |
| `interface.py` | `MarketDataSource` ABC |
| `simulator.py` | `GBMSimulator`, `SimulatorDataSource` (see `MARKET_SIMULATOR.md`) |
| `seed_prices.py` | Seed prices, per-ticker GBM params, correlation groups |
| `massive_client.py` | `MassiveDataSource` |
| `factory.py` | `create_market_data_source()` |
| `stream.py` | `create_stream_router()` — SSE endpoint |
| `__init__.py` | Public exports |

Public imports:

```python
from app.market import PriceCache, PriceUpdate, MarketDataSource, create_market_data_source, create_stream_router
```

## 3. `PriceUpdate` — the one price type

```python
@dataclass(frozen=True, slots=True)
class PriceUpdate:
    """Immutable snapshot of one ticker's price."""

    ticker: str
    price: float
    previous_price: float           # price at the previous update (drives flash up/down)
    timestamp: float                # Unix seconds
    prev_close: float | None = None # previous session close (drives "daily change %")

    @property
    def change(self) -> float: ...           # price - previous_price
    @property
    def change_percent(self) -> float: ...   # tick-to-tick %
    @property
    def direction(self) -> str: ...          # "up" | "down" | "flat"
    @property
    def day_change_percent(self) -> float | None: ...  # vs prev_close

    def to_dict(self) -> dict: ...           # JSON for SSE / REST
```

Two kinds of "change" exist and must not be confused:

- **Tick change** (`previous_price`, `direction`) — drives the green/red flash animation.
- **Daily change** (`prev_close`, `day_change_percent`) — the watchlist's "daily change %"
  column. From Massive this is `prevDay.c`; in the simulator it is the seed price at startup.

SSE/JSON shape (`to_dict()`):

```json
{"ticker": "AAPL", "price": 190.52, "previous_price": 190.48, "timestamp": 1794067200.5,
 "change": 0.04, "change_percent": 0.021, "direction": "up",
 "prev_close": 190.0, "day_change_percent": 0.2737}
```

## 4. `PriceCache`

```python
class PriceCache:
    """Thread-safe latest-price store. One writer (the data source), many readers."""

    def update(self, ticker: str, price: float, timestamp: float | None = None,
               prev_close: float | None = None) -> PriceUpdate: ...
    def get(self, ticker: str) -> PriceUpdate | None: ...
    def get_price(self, ticker: str) -> float | None: ...
    def get_all(self) -> dict[str, PriceUpdate]: ...      # shallow copy
    def remove(self, ticker: str) -> None: ...
    @property
    def version(self) -> int: ...   # bumps on every update; SSE sends only when it changes
```

- First update for a ticker: `previous_price = price` (direction `flat`).
- `prev_close=None` keeps the ticker's existing `prev_close`, so producers only pass it when
  they know it.
- Prices are rounded to 2 dp at the cache boundary.
- A `threading.Lock` is used (not `asyncio.Lock`) because the Massive fetch runs in a worker
  thread and the cache must be safe from any thread.

## 5. `MarketDataSource` — the interface

```python
class MarketDataSource(ABC):
    """Produces prices into a PriceCache on its own schedule."""

    @abstractmethod
    async def start(self, tickers: list[str]) -> None:
        """Seed the cache and start the background task. Call once."""

    @abstractmethod
    async def stop(self) -> None:
        """Cancel the background task. Safe to call twice."""

    @abstractmethod
    async def add_ticker(self, ticker: str) -> None:
        """Track a ticker. No-op if present."""

    @abstractmethod
    async def remove_ticker(self, ticker: str) -> None:
        """Stop tracking a ticker and remove it from the cache. No-op if absent."""

    @abstractmethod
    def get_tickers(self) -> list[str]:
        """Currently tracked tickers."""
```

| Behaviour | Simulator | Massive |
|---|---|---|
| Cadence | 0.5 s | `MASSIVE_POLL_INTERVAL` (default 15 s) |
| `start()` | Cache seeded synchronously from seed prices | One immediate poll, then loop |
| `add_ticker()` | Price available immediately | Price appears on next poll (≤ 60 s in `eod` mode) |
| Unknown ticker | Seed price derived from the ticker name ($50–$300, stable across restarts) | Never appears in cache (Massive returns nothing) |
| Ticker case | Normalised with `normalize_ticker()` (strip + upper-case) | Same |
| Market closed | Keeps ticking | Prices freeze at last session |

Callers must therefore tolerate `cache.get_price(t) is None` briefly after `add_ticker()`
(Massive). Trade execution should reject a trade with "no price available yet" in that case.

## 6. Factory

```python
def create_market_data_source(price_cache: PriceCache) -> MarketDataSource:
    """MassiveDataSource if MASSIVE_API_KEY is non-empty, else SimulatorDataSource."""
    api_key = os.environ.get("MASSIVE_API_KEY", "").strip()
    if api_key:
        interval = max(float(os.environ.get("MASSIVE_POLL_INTERVAL") or 15), 1.0)
        return MassiveDataSource(api_key, price_cache, poll_interval=interval)
    return SimulatorDataSource(price_cache)
```

`MASSIVE_POLL_INTERVAL` is optional (in `.env.example`); empty means 15 s and values below
1 s are raised to 1 s. Paid plans have no call limit, so 2–5 s is reasonable there.

## 7. `MassiveDataSource` — design

### 7.1 Two modes, chosen automatically

The free Basic plan **cannot call snapshots** (EOD data only). Rather than a second config
variable, the source detects this on its first poll:

| Mode | Endpoint | Used when | Interval |
|---|---|---|---|
| `snapshot` | `GET /v2/snapshot/locale/us/markets/stocks/tickers?tickers=...` | Default (Starter+) | `poll_interval` |
| `eod` | `GET /v2/aggs/grouped/locale/us/market/stocks/{date}` | Snapshot returned 403 `NOT_AUTHORIZED` | max(`poll_interval`, 3600 s); 60 s while a ticker has no price (§7.3) |

Both are one API call per poll, whatever the watchlist size. In `eod` mode prices are the
latest daily close and don't move intraday — the app still works, but shows a static
market. Log a clear warning when switching.

### 7.2 Price extraction (per snapshot)

Fields depend on the plan (`lastTrade` only on Developer+), so take the first present:

```python
def snapshot_price(snap: TickerSnapshot) -> float | None:
    """Best available current price for a snapshot, by plan richness."""
    if snap.last_trade and snap.last_trade.price:
        return snap.last_trade.price
    if snap.min and snap.min.close:
        return snap.min.close
    if snap.day and snap.day.close:
        return snap.day.close
    if snap.prev_day and snap.prev_day.close:
        return snap.prev_day.close
    return None
```

Timestamp: `snap.updated / 1e9` (nanoseconds). Fall back to `time.time()` if `updated` is
`None`. `prev_close`: `snap.prev_day.close`.

### 7.3 Implementation notes

The code is `backend/app/market/massive_client.py` (no copy here, to avoid drift). Behaviour
beyond §7.1–7.2, added after the 2026-11-07 review (`MARKET_DATA_REVIEW.md`):

- **Request timeout.** massive 2.2.0 builds a `urllib3.Timeout` but never applies it, so a
  stalled connection would block the poller forever. `MassiveDataSource(request_timeout=10)`
  installs it on the client's connection pool.
- **No resurrection.** Poll results are written under a lock, and only for tickers still
  tracked, so a ticker removed while a poll is in flight stays removed.
- **EOD retry.** In `eod` mode the next poll is due after `EOD_RETRY_INTERVAL` (60 s) while
  any tracked ticker has no cached price (failed first poll, newly added ticker), otherwise
  after max(`poll_interval`, 3600 s). The loop wakes every min(`poll_interval`, 60 s) to
  check. A first poll can cost 1 snapshot (403) + up to 5 grouped-daily calls (Monday
  morning), so it may hit the Basic 5 calls/min limit; the retry a minute later succeeds.
- **Market date.** "Today" for grouped-daily is the US/Eastern date, not the server's.
- The `"NOT_AUTHORIZED"` string match is based on the documented Polygon error body; confirm
  it with a free key and adjust if the body differs (§9).

## 8. Changes Needed to the Current Code

Found during research — each verified against SDK 2.2.0, which is pinned in `uv.lock`:

| # | Problem in current code | Evidence | Fix |
|---|---|---|---|
| 1 | `snap.last_trade.timestamp` doesn't exist. Every snapshot raises `AttributeError` and is skipped, so **Massive mode never fills the cache** | `hasattr(TickerSnapshot.from_dict({...}).last_trade, "timestamp") → False`; the field is `sip_timestamp` | Use `snap.updated` |
| 2 | Timestamp treated as ms (`/ 1000`) | Snapshot `updated`/`lastTrade.t` are 19-digit nanoseconds | `/ 1e9` |
| 3 | Price read only from `last_trade` | `lastTrade` absent on Starter (no trades entitlement) | `snapshot_price()` fallback chain (§7.2) |
| 4 | Free Basic key fails every poll | Snapshots "Not included" on Basic | Auto `eod` mode (§7.1) |
| 5 | No daily change % | Watchlist needs "daily change %" (PLAN §10) | Add `prev_close` to `PriceUpdate`/`PriceCache.update` |
| 6 | Tests mock a fake attribute | `tests/market/test_massive.py` sets `snap.last_trade.timestamp` on a `MagicMock` | Build fixtures with `TickerSnapshot.from_dict({...real JSON...})` so tests fail if field names are wrong |
| 7 | Poll interval hard-coded | PLAN §6 says configurable | `MASSIVE_POLL_INTERVAL` env var |

Suggested order (each step small and tested): 6 → 1+2 → 3 → 5 → 7 → 4.

## 9. Open Questions

- Exact 403 body for a snapshot call on a Basic key — confirm with a real free key before
  relying on the `NOT_AUTHORIZED` match.
- Should the UI show "delayed 15 min" / "end-of-day" when in Massive mode? A `mode` field could
  be exposed via `/api/health`.

## 10. Wiring into FastAPI

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.market import PriceCache, create_market_data_source, create_stream_router

price_cache = PriceCache()
market = create_market_data_source(price_cache)

@asynccontextmanager
async def lifespan(app: FastAPI):
    await market.start(load_watchlist_tickers())   # from the watchlist table
    yield
    await market.stop()

app = FastAPI(lifespan=lifespan)
app.include_router(create_stream_router(price_cache))
```

Downstream usage:

```python
# Watchlist routes
await market.add_ticker("PYPL")       # POST /api/watchlist
await market.remove_ticker("PYPL")    # DELETE /api/watchlist/{ticker}
# Removing from the watchlist while a position is held: keep tracking it,
# because the portfolio still needs a price for valuation.

# Trade execution
price = price_cache.get_price(ticker)
if price is None:
    raise TradeError(f"No price available for {ticker}")

# Portfolio valuation / LLM context
prices = price_cache.get_all()
value = cash + sum(p.quantity * prices[p.ticker].price for p in positions if p.ticker in prices)
```

The tracked set should be **watchlist ∪ held positions**, so a sold-from-watchlist holding
still has a live price.
