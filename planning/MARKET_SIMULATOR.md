# Market Simulator — Approach and Code Structure

The default market data source when `MASSIVE_API_KEY` is not set. It produces realistic,
correlated, live-looking prices with no network, no API key and no cost. It implements the
`MarketDataSource` interface (`MARKET_INTERFACE.md`) and writes into the shared `PriceCache`,
so the rest of the app cannot tell it apart from real data.

Code: `backend/app/market/simulator.py` and `backend/app/market/seed_prices.py`.

---

## 1. Goals

| Goal | How |
|---|---|
| Looks like a live market | Small moves every 500 ms, so prices flash constantly |
| Realistic statistics | Geometric Brownian Motion (log-normal, never negative) |
| Stocks move together | Correlated random shocks via Cholesky decomposition |
| Some drama | Rare 2–5 % jumps on single tickers |
| Realistic starting point | Seed prices near real values (AAPL ~$190 ...) |
| Dynamic watchlist | Add/remove tickers at runtime |
| Cheap | NumPy vector draw + loop over < 50 tickers every 0.5 s |

Non-goals: order books, bid/ask spreads, market hours, intraday seasonality, mean reversion.

## 2. The Model — Geometric Brownian Motion

Each tick, every price is multiplied by a log-normal factor:

```
S(t+dt) = S(t) · exp( (μ − σ²/2)·dt + σ·√dt·Z )
```

| Symbol | Meaning | Source |
|---|---|---|
| `S(t)` | Current price | Seeded, then evolves |
| `μ` | Annualised drift (expected return) | `TICKER_PARAMS[t]["mu"]` |
| `σ` | Annualised volatility | `TICKER_PARAMS[t]["sigma"]` |
| `dt` | Tick length as a fraction of a trading year | `0.5 / (252 · 6.5 · 3600) ≈ 8.48e-8` |
| `Z` | Standard normal shock, correlated across tickers | Cholesky (§3) |

Why GBM: it is the standard textbook stock model (Black–Scholes), prices stay positive, and
percentage moves scale with volatility — so a $800 NVDA moves more dollars per tick than a
$195 JPM, as in reality. The `−σ²/2` term is the Itô correction that keeps the expected
price growth equal to `μ`.

Why that `dt`: time runs at real speed over the trading year (252 days × 6.5 h). An hour of
simulation therefore has the volatility of a real trading hour:

```
1-hour std = σ · √(1/1638)   → AAPL (σ=0.22): 0.54 %   TSLA (σ=0.50): 1.24 %
```

Measured on the current code (7,200 ticks = 1 simulated hour, events off):

| Metric | AAPL | TSLA | JPM |
|---|---|---|---|
| 1-hour std, measured | 0.58 % | 1.25 % | 0.48 % |
| 1-hour std, theory | 0.54 % | 1.24 % | 0.45 % |

Median tick-to-tick move: AAPL 1¢, TSLA 3¢, NVDA 6¢ — enough to make prices flash almost
every tick without looking wild.

> Drift is negligible at this timescale (μ·dt ≈ 4e-9 per tick). It is kept for correctness
> and in case `dt` is ever scaled up to "fast-forward" the market.

## 3. Correlated Moves — Cholesky Decomposition

Real stocks share a market factor; tech names move together. Draw `n` independent normals
and multiply by the lower-triangular Cholesky factor `L` of the target correlation matrix `C`
(`C = L·Lᵀ`):

```python
z_independent = np.random.standard_normal(n)
z_correlated  = L @ z_independent      # Cov(z_correlated) == C
```

Correlation is defined by sector (`seed_prices.py`):

| Pair | ρ | Constant |
|---|---|---|
| Tech ↔ tech (AAPL, GOOGL, MSFT, AMZN, META, NVDA, NFLX) | 0.6 | `INTRA_TECH_CORR` |
| Finance ↔ finance (JPM, V) | 0.5 | `INTRA_FINANCE_CORR` |
| TSLA ↔ anything | 0.3 | `TSLA_CORR` |
| Cross-sector / unknown tickers | 0.3 | `CROSS_GROUP_CORR` |

```python
def _pairwise_correlation(t1: str, t2: str) -> float:
    if "TSLA" in (t1, t2):
        return TSLA_CORR
    if t1 in tech and t2 in tech:
        return INTRA_TECH_CORR
    if t1 in finance and t2 in finance:
        return INTRA_FINANCE_CORR
    return CROSS_GROUP_CORR
```

Measured tick-return correlations: AAPL–MSFT 0.55, JPM–V 0.46, AAPL–JPM 0.27, TSLA–AAPL 0.28
— slightly below target because the 2 dp rounding of output prices adds uncorrelated noise.
That is fine for a demo.

The matrix is rebuilt (`_rebuild_cholesky`, O(n³), trivial for n < 50) whenever a ticker is
added or removed. This block structure (a constant floor of 0.3 plus higher within-group
values) is always positive definite, so `np.linalg.cholesky` will not fail. **If you add
groups or change the numbers, keep within-group ρ ≥ cross-group ρ** or the matrix may become
invalid.

## 4. Random Events

After the GBM step, each ticker independently has `event_probability` (default `0.001`) of
a shock:

```python
if random.random() < self._event_prob:
    magnitude = random.uniform(0.02, 0.05)
    self._prices[ticker] *= 1 + magnitude * random.choice([-1, 1])
```

Rate: 10 tickers × 2 ticks/s × 0.001 = **one event every ~50 s** (measured: 74 per
simulated hour vs 72 expected). Events are permanent level shifts (no reversion), like a
news jump. They give the heatmap, P&L chart and the AI assistant something to talk about.

## 5. Seed Data and Parameters (`seed_prices.py`)

```python
SEED_PRICES = {"AAPL": 190.00, "GOOGL": 175.00, "MSFT": 420.00, "AMZN": 185.00, "TSLA": 250.00,
               "NVDA": 800.00, "META": 500.00, "JPM": 195.00, "V": 280.00, "NFLX": 600.00}

TICKER_PARAMS = {
    "AAPL": {"sigma": 0.22, "mu": 0.05}, "GOOGL": {"sigma": 0.25, "mu": 0.05},
    "MSFT": {"sigma": 0.20, "mu": 0.05}, "AMZN": {"sigma": 0.28, "mu": 0.05},
    "TSLA": {"sigma": 0.50, "mu": 0.03}, "NVDA": {"sigma": 0.40, "mu": 0.08},
    "META": {"sigma": 0.30, "mu": 0.05}, "JPM": {"sigma": 0.18, "mu": 0.04},
    "V":    {"sigma": 0.17, "mu": 0.04}, "NFLX": {"sigma": 0.35, "mu": 0.05},
}
DEFAULT_PARAMS = {"sigma": 0.25, "mu": 0.05}   # tickers added at runtime
```

Volatilities are close to the real long-run implied vols of each name. Tickers outside
the table (e.g. the user adds `PYPL`) get `DEFAULT_PARAMS`, a random seed price between $50 and $300,
and cross-sector correlation 0.3. To make a new ticker realistic, add it to these dicts —
no code change needed.

## 6. Code Structure

Two classes with a clean split: **pure math** vs **async plumbing**.

```
simulator.py
├── GBMSimulator            pure, synchronous, no I/O — easy to unit test
│   ├── __init__(tickers, dt, event_probability)
│   ├── step() -> dict[str, float]          one tick for all tickers (hot path)
│   ├── add_ticker(t) / remove_ticker(t)     + rebuild Cholesky
│   ├── get_price(t) / get_tickers()
│   ├── _add_ticker_internal(t)              seed price + params, no rebuild (batch init)
│   ├── _rebuild_cholesky()
│   └── _pairwise_correlation(t1, t2)        static, sector rules
│
└── SimulatorDataSource(MarketDataSource)   async adapter to PriceCache
    ├── start(tickers)    build GBMSimulator, seed cache, create task "simulator-loop"
    ├── stop()            cancel task
    ├── add_ticker(t)     sim.add_ticker + seed cache immediately
    ├── remove_ticker(t)  sim.remove_ticker + cache.remove
    ├── get_tickers()
    └── _run_loop()       while True: step → cache.update each → sleep(0.5)
```

### 6.1 `GBMSimulator.step()` (hot path)

```python
def step(self) -> dict[str, float]:
    """Advance all tickers one tick. Returns {ticker: rounded_price}."""
    n = len(self._tickers)
    if n == 0:
        return {}
    z = np.random.standard_normal(n)
    if self._cholesky is not None:          # None when n == 1
        z = self._cholesky @ z
    result = {}
    for i, ticker in enumerate(self._tickers):
        mu, sigma = self._params[ticker]["mu"], self._params[ticker]["sigma"]
        self._prices[ticker] *= math.exp((mu - 0.5 * sigma**2) * self._dt
                                         + sigma * math.sqrt(self._dt) * z[i])
        self._maybe_apply_event(ticker)     # the §4 block (inlined in current code)
        result[ticker] = round(self._prices[ticker], 2)
    return result
```

Internal prices stay **unrounded**; only the output is rounded. Rounding internally would
add drift and, for low-priced tickers, freeze them.

### 6.2 `SimulatorDataSource._run_loop()`

```python
async def _run_loop(self) -> None:
    """Step, publish to cache, sleep. A failed step is logged, never kills the loop."""
    while True:
        try:
            for ticker, price in self._sim.step().items():
                self._cache.update(ticker=ticker, price=price)
        except Exception:
            logger.exception("Simulator step failed")
        await asyncio.sleep(self._interval)
```

- Runs on the event loop (no thread). The step takes microseconds, so it never blocks.
- `start()` seeds the cache **before** the first tick, so SSE clients get prices instantly.
- `add_ticker()` seeds the cache immediately, so a newly added ticker appears in the
  watchlist (and is tradeable) without waiting for the next tick.

### 6.3 Daily change (`prev_close`)

To support the watchlist "daily change %" (see `MARKET_INTERFACE.md` §3), the simulator
treats the **seed price as the previous close**: pass `prev_close=seed` on every
`cache.update`, or once at seeding (the cache keeps it). Then `day_change_percent` reads like
a real "since yesterday's close" figure that drifts as the session runs.

## 7. Testing

`GBMSimulator` is deterministic when NumPy and `random` are seeded, so tests can assert exact
behaviour (`tests/market/test_simulator.py`, `test_simulator_source.py`):

| Test | Assertion |
|---|---|
| Positivity | 10k steps → all prices > 0 |
| Statistics | log-return std over many ticks ≈ `σ·√dt` (within tolerance) |
| Correlation | sample corr(AAPL, MSFT) > corr(AAPL, JPM) |
| Events | `event_probability=1.0` → every tick moves 2–5 % beyond GBM; `0.0` → none |
| Dynamic tickers | add → price present & Cholesky shape (n×n); remove → gone; duplicates no-op |
| Unknown ticker | gets `DEFAULT_PARAMS` and a seed in [50, 300] |
| Single ticker | `_cholesky is None`, `step()` still works |
| Data source | after `start()` cache has all tickers; after ~1 s versions have advanced; `stop()` idempotent |

For full reproducibility, a small improvement would be to give `GBMSimulator` its own
`np.random.Generator` (`seed: int | None = None` argument) and use it for both the normals and
the event draws, instead of the global `np.random` and `random` modules.

## 8. Tuning Knobs

| Knob | Where | Effect |
|---|---|---|
| `update_interval` | `SimulatorDataSource(...)` | Tick cadence (default 0.5 s; keep in sync with SSE 0.5 s) |
| `dt` | `GBMSimulator(...)` | Time compression: ×60 makes a minute look like an hour |
| `event_probability` | both constructors | Frequency of jumps |
| `sigma` / `mu` | `TICKER_PARAMS` | Per-ticker volatility / drift |
| Correlations | `seed_prices.py` constants, `CORRELATION_GROUPS` | Co-movement |

Run `uv run market_data_demo.py` in `backend/` to watch the result in a live terminal
dashboard.
