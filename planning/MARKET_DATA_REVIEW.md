# Market Data Backend — Code Review

**Date:** 2026-11-07
**Scope:** `backend/app/market/` (8 modules, 391 statements), `backend/tests/market/` (7 test modules), `backend/pyproject.toml`, the market-data docs in `planning/`.
**Previous review:** `planning/archive/MARKET_DATA_REVIEW.md` (2026-02-10). All of its findings and the `MARKET_INTERFACE.md` §8 fixes are in place.
**Status:** All findings resolved — see §7.

---

## 1. Verdict

The subsystem is in good shape: small, readable, well-documented, and the design matches PLAN.md §6. All tests pass and the GBM math checks out empirically. It is **ready for downstream work**, with the four medium-severity issues below (M1–M4) worth fixing first. Three of them only affect the optional Massive path. M4 (ticker normalisation) and L1 (random seeds for unknown tickers) affect the default simulator and the portfolio code that will be built on top of it.

## 2. Verification Performed

| Check | Command | Result |
|---|---|---|
| Unit tests | `uv run --extra dev pytest --cov=app` | **106 passed** in 1.6 s |
| Coverage | (same) | **98%** (391 stmts, 9 missed: `massive_client.py:89-91`, `simulator.py:155,276-277`, `stream.py:37,85-86`) |
| Lint | `uv run --extra dev ruff check app/ tests/ market_data_demo.py` | All checks passed |
| Format | `uv run --extra dev ruff format --check app tests` | **5 files would be reformatted** (see L7) |
| Live SSE | uvicorn + `curl -N /api/stream/prices` with the simulator | `retry: 1000` then a `data:` event every ~500 ms with the documented shape; clean startup/shutdown |
| GBM statistics | 20,000 steps of AAPL+GOOGL, events off | per-tick log-return std **6.45e-5** vs expected σ√dt = **6.41e-5**; realised AAPL/GOOGL correlation **0.604** vs target 0.6 |
| Cholesky stability | 60 tickers (all groups + 50 unknown) | Positive-definite, decomposes fine |
| Bug probes | scratchpad script (cases below) | M2, M3, M4, L2, L3 reproduced |

Locked versions are current: fastapi 0.128.7, starlette 0.52.1, uvicorn 0.40.0, numpy 2.4.2, massive 2.2.0, pytest-asyncio 1.3.0.

Note: the test suite ran on Python 3.13 (the local `.venv`), while PLAN.md §11 targets Python 3.12 in Docker. `requires-python = ">=3.12"` allows both. Run the suite once under 3.12 when the Dockerfile exists.

## 3. Strengths

- **A clean strategy pattern.** One ABC and two implementations behind a factory. Consumers only touch `PriceCache`.
- **A single price type.** `PriceUpdate` is frozen, uses slots, and keeps tick change (flash) and daily change (`prev_close`) distinct.
- **Correct GBM.** It uses the exact log-normal step with Itô correction and Cholesky-correlated shocks, and the measured results match theory (above).
- **Robust Massive client.** It uses one batched snapshot call per poll and a sensible price fallback chain across plan tiers (`lastTrade → min → day → prevDay`). It falls back automatically to end-of-day prices on free keys, and it runs blocking I/O in `asyncio.to_thread`.
- **Tests built from real SDK models.** `TickerSnapshot.from_dict` / `GroupedDailyAgg.from_dict` replace `MagicMock` attributes, so a wrong field name fails the tests.
- **A router factory.** The SSE router is built per call, which fixes the earlier duplicate-route bug.
- **Good docs.** `backend/CLAUDE.md` and `MARKET_INTERFACE.md` are accurate against the code.

---

## 4. Findings

Severity: **M** = medium (wrong behaviour that users can hit), **L** = low (edge case, hygiene or test quality).

### M1 — Massive HTTP calls have no timeout; one hung request freezes the poller forever

`massive` 2.2.0 builds `self.timeout = urllib3.Timeout(connect=10, read=10)` in `rest/base.py:81` but never passes it to `self.client.request(...)` (`base.py:118`) or to the `PoolManager`. A stalled TCP connection therefore blocks the worker thread indefinitely. Because `_poll_loop` awaits `_poll_once`, nothing raises, nothing is logged, and prices silently stop updating.

*Evidence:* code reading of the installed SDK (`grep -rn "self.timeout\|timeout=" massive/rest/` shows only the assignment). I did not reproduce it with a real stalled socket.

*Fix (simple):* bound the call in `_poll_once`, e.g. `await asyncio.wait_for(asyncio.to_thread(...), timeout=30)`, or rebuild `self._client.client` as a `PoolManager` with `timeout=`. Consider reporting this upstream.

### M2 — A ticker removed during an in-flight Massive poll comes back in the cache

`remove_ticker()` deletes the ticker from the cache, but a poll already running in the worker thread still writes it back. The ticker then sits in the cache and is pushed over SSE indefinitely, and it is never updated again because it is no longer tracked. The same applies to `_poll_eod`, which captures `wanted` up front.

*Evidence (reproduced):* a mocked `get_snapshot_all` that sleeps 200 ms, with `remove_ticker("GOOGL")` called mid-poll → `tracked=['AAPL']`, `'GOOGL' in cache == True`.

*Fix:* in `_poll_snapshots` / `_poll_eod`, skip tickers no longer in `self._tickers` at write time (`if snap.ticker not in self._tickers: continue`).

### M3 — The free-key (EOD) path can exceed 5 calls/min on its first poll and then shows no prices for an hour

On a Basic key, the first poll costs 1 snapshot call (403) plus one grouped-daily call per day walked back. On a Monday, or after a holiday, that is Mon (today, empty) → Sun → Sat → Fri → Thu = **6 calls**, above the documented 5/min limit. Any failure aborts the whole `_poll_eod`, which throws away the days already fetched. The next attempt only comes after `EOD_MIN_INTERVAL` = 1 hour.

*Evidence:* call count reproduced with mocks (`grouped calls=5 + 1 snapshot = 6`). The 429 itself is inferred: urllib3 retries 429 only ~3× with a 0.1 s backoff factor, far short of a one-minute window.

Related: in EOD mode a ticker added via `add_ticker()` gets no price for up to an hour, so trades in it fail for that long.

*Fix options (pick one, keep it simple):* shorten the retry interval after a failed EOD poll (e.g. 60 s) until the first success, and/or fetch the latest close for a newly added ticker on the next short cycle. Also confirm the real 403/429 bodies with a free key (already an open question in `MARKET_INTERFACE.md` §9).

### M4 — Ticker normalisation is inconsistent between sources

`MassiveDataSource` upper-cases and strips tickers in `start`, `add_ticker` and `remove_ticker`; `SimulatorDataSource` / `GBMSimulator` do neither. In simulator mode `add_ticker("aapl")` and `add_ticker(" tsla")` create new, distinct tickers with random seed prices.

*Evidence (reproduced):* `tickers=['AAPL', 'aapl', ' tsla']`.

This breaks the "source-agnostic" contract. A watchlist or LLM bug that passes lower-case input would behave differently depending on the env var.

*Fix:* normalise in `SimulatorDataSource` the same way (one line per method), and state in the `MarketDataSource` docstrings that tickers are normalised.

### L1 — Unknown tickers get a new random price on every restart

`_add_ticker_internal` seeds unknown tickers with `random.uniform(50, 300)`. Once the portfolio exists, a user who buys e.g. PYPL at a simulated $123 could find it re-seeded at $280 after a container restart: a large, fake P&L jump. Known tickers also reset to their seed on restart, but the jump there is small and plausible.

*Fix:* make the seed deterministic per ticker, e.g. `random.Random(ticker).uniform(50, 300)`. Optionally, downstream code could re-seed from the last traded price.

### L2 — An empty `MASSIVE_POLL_INTERVAL` crashes startup

`float(os.environ.get("MASSIVE_POLL_INTERVAL", "15"))` raises `ValueError: could not convert string to float: ''` when the variable is present but empty (a common `.env` state). There is also no lower bound, so `0` would hammer the API.

*Evidence (reproduced).*

*Fix:* `float(os.environ.get("MASSIVE_POLL_INTERVAL") or 15)`, optionally with `max(…, 1.0)`.

### L3 — `PriceCache.remove()` does not bump `version`

SSE clients only see a removal at the next `update()`: ~500 ms in the simulator, 15 s with Massive, up to 1 h in EOD mode.

*Evidence (reproduced):* the version is unchanged after `remove`.

*Fix:* `self._version += 1` in `remove()`.

### L4 — SSE sends nothing while the cache is idle

The generator only yields when `version` changes. In EOD mode that means about an hour of silence. Idle connections may be cut by proxies or load balancers (relevant to the App Runner/Render stretch goal), and the client can't tell a stale feed from a dead one.

*Fix:* yield an SSE comment (`": ping\n\n"`) every ~15 s when nothing has changed.

### L5 — The SSE generator swallows `CancelledError`

`stream.py:85-86` catches `asyncio.CancelledError` and returns. Swallowing cancellation is an asyncio anti-pattern and can interfere with Starlette/anyio cancel scopes on shutdown.

*Fix:* log in a `finally:` block, or re-raise after logging. These are also the uncovered lines.

### L6 — `date.today()` uses local time, not US/Eastern

In a UTC container after 19:00/20:00 ET, "today" is already tomorrow in ET, which costs one extra empty grouped-daily call (it also feeds M3).

*Fix:* `datetime.now(ZoneInfo("America/New_York")).date()`.

### L7 — Formatting and dependency hygiene

- `ruff format --check` fails on `massive_client.py`, `test_massive.py`, `test_models.py`, `test_simulator.py` and `test_simulator_source.py`. Run `uv run ruff format app tests`.
- `rich` is a runtime dependency but is only used by `market_data_demo.py`. Move it to dev.
- Dev tools are under `[project.optional-dependencies] dev`, so every command needs `--extra dev`. Current uv practice is `[dependency-groups]` (`uv add --dev pytest …`), after which `uv run pytest` just works. Update `backend/CLAUDE.md` accordingly.
- `tests/conftest.py` overrides the `event_loop_policy` fixture with `asyncio.DefaultEventLoopPolicy()`. That is redundant, and the class is deprecated in Python 3.14. Delete the fixture.
- `@pytest.mark.asyncio` decorators are redundant with `asyncio_mode = "auto"`.

### L8 — Test-suite gaps and weak tests

Coverage is high, but a few tests assert less than their names claim:

- `test_exception_resilience` never injects an exception, so it only checks that the task is still running. Make `step()` raise once (patch it) and assert that updates resume.
- `test_custom_event_probability` asserts nothing.
- `test_prices_rounded_to_two_decimals` checks `str(price)`. Prefer `round(p, 2) == p`.
- PLAN.md §12 asks that "GBM math is correct", but no test checks the distribution or the correlation. Add a seeded statistical test like the probe above (std within ~5% of σ√dt, corr ≈ 0.6).
- There is no HTTP-level SSE test. One `httpx.AsyncClient(transport=ASGITransport(app))` test of `/api/stream/prices` would cover `stream.py:37` and the response headers.
- `_poll_loop` (`massive_client.py:89-91`) is untested.
- Several async tests rely on `asyncio.sleep` timing (0.05–0.3 s) and may be flaky on slow CI. Prefer asserting on `cache.version` after a bounded wait loop.
- Tests reach into private attributes (`_tickers`, `_cholesky`, `_client`, `_interval`). That is acceptable for unit tests, but it couples them to internals.

### L9 — Documentation drift

`MARKET_DATA_SUMMARY.md`'s test table is from the original build: 6 modules, Massive coverage 56%, overall 84%. It now contradicts the header line (106 tests, 98%). Refresh the table or drop it.

---

## 5. Observations (no action required)

- **Tick size:** the typical simulator move is ~$0.012 per tick on AAPL. After rounding to cents, about a third of ticks are "flat", so not every SSE event flashes. That looks natural.
- **Daily change:** in the simulator, "daily change %" is the change since process start, because the seed is used as `prev_close`. This is documented and fine for a demo.
- **Payload:** SSE pushes the full snapshot (~250 B per ticker) every 500 ms, which is negligible at watchlist scale. The frontend should treat each event as the complete state, so removals are implicit.
- **Tracked set:** `remove_ticker()` also drops the ticker from the cache. As `MARKET_INTERFACE.md` §10 notes, the watchlist routes must keep tracking tickers that are still held as positions (tracked set = watchlist ∪ positions), or portfolio valuation loses their price.
- **Lifecycle:** `start()` twice and `add_ticker()` before `start()` are undefined or ignored, which is documented in the ABC. This is acceptable given the single lifespan owner.

## 6. Recommended Order

1. L7 formatting, plus moving to `[dependency-groups]` (mechanical, removes noise).
2. M4 normalisation and L1 deterministic seeds (these affect the default simulator path that every user runs).
3. L2, L3, L5 (one-line fixes).
4. M2 and M1 (Massive robustness).
5. M3 and L6 (free-key path; verify with a real Basic key first).
6. L4 keepalive and L8 test improvements, alongside the FastAPI app wiring.

---

## 7. Resolution (2026-11-07, branch `market-data-review-fixes`)

All findings are fixed. Each fix has a test that failed before the change (M1 was also reproduced directly: a `RESTClient` with `read_timeout=0.1` was still blocked after 3 s against a socket that never replies).

| # | Fix | Test(s) |
|---|---|---|
| M1 | `MassiveDataSource(request_timeout=10)` installs the SDK's unused `Timeout` on the urllib3 pool (`connection_pool_kw["timeout"]`) | `test_request_times_out_on_silent_server` |
| M2 | `_write()` checks `ticker in self._tickers` under a lock shared with `remove_ticker()` | `test_ticker_removed_during_poll_stays_removed`, `test_eod_ticker_removed_during_poll_stays_removed` |
| M3 | `EOD_RETRY_INTERVAL` = 60 s while any tracked ticker has no price; the loop wakes every min(interval, 60 s) | `TestPollScheduling` |
| M4 | `normalize_ticker()` in `interface.py`, used by both sources, exported from `app.market` | `test_tickers_are_normalized`, `test_add_ticker_normalizes` |
| L1 | `random.Random(ticker).uniform(50, 300)` seed | `test_unknown_ticker_seed_is_deterministic` |
| L2 | `max(float(env or 15), 1.0)` | `test_empty_poll_interval_uses_default`, `test_poll_interval_has_floor` |
| L3 | `remove()` bumps `version` when it removed something | `test_remove_bumps_version`, `test_remove_unknown_keeps_version` |
| L4 | `: ping` after 15 s idle | `test_keepalive_when_idle` |
| L5 | Logging moved to `finally:`, cancellation propagates. SSE now also sends `{}` when the last ticker is removed | `test_removal_of_last_ticker_sends_empty_snapshot` |
| L6 | `datetime.now(ZoneInfo("America/New_York")).date()` | `test_eod_uses_us_eastern_date` |
| L7 | `[dependency-groups] dev` (incl. `rich`), conftest and redundant markers removed, `ruff format` applied | `ruff format --check` clean |
| L8 | GBM σ and correlation statistics, Cholesky with 60 tickers, real exception injection, event-probability assertion, cents rounding, route-level SSE test, poll-loop tests; bounded `wait_until` instead of fixed sleeps | — |
| L9 | `MARKET_DATA_SUMMARY.md`, `MARKET_INTERFACE.md`, `MARKET_SIMULATOR.md` and `backend/CLAUDE.md` updated; the stale code copy in `MARKET_INTERFACE.md` §7.3 replaced by notes | — |

Note on L8: an HTTP-level test through `httpx.ASGITransport` is not possible, because that transport buffers the full response body and never returns for an endless SSE stream (verified: the test hung). The route test calls the endpoint directly instead. The live stream was verified with uvicorn + `curl -N`.

**Final state:** 126 tests pass (stable over repeated runs), 100% line coverage, `ruff check` and `ruff format --check` clean.

**Still open:** the exact 403/429 bodies from a real Basic key (`MARKET_INTERFACE.md` §9).
