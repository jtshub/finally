# Team Contract — FinAlly Build

Shared contract for the agent team. `PLAN.md` is the spec; this file fixes the seams between
team members so they can work in parallel. If you need to change a seam, edit this file and
message the affected teammates.

## Team & File Ownership

Only edit files you own. Ask the owner (via SendMessage) for changes elsewhere.

| Member | Name | Owns |
|---|---|---|
| Database Engineer | `db-engineer` | `backend/app/db/`, `backend/tests/db/` |
| LLM Engineer | `llm-engineer` | `backend/app/llm/`, `backend/tests/llm/` |
| Backend API Engineer | `backend-api` | `backend/app/main.py`, `backend/app/api/`, `backend/app/services/`, `backend/tests/api/`, `backend/tests/services/`, `backend/pyproject.toml` (others may `uv add`) |
| Frontend Engineer | `frontend-engineer` | `frontend/` |
| DevOps Engineer | `devops-engineer` | `Dockerfile`, `.dockerignore`, `docker-compose.yml`, `scripts/start_*`, `scripts/stop_*`, `db/.gitkeep`, `.gitignore` |
| Integration Tester | `integration-tester` | `test/` (Playwright + `test/docker-compose.test.yml`), `planning/ISSUES.md` |

`backend/app/market/` is complete — do not modify it without the lead's approval.
Nobody commits; the lead commits.

## Backend Module Seams

### `app.db` (db-engineer) — stdlib `sqlite3`, plain functions, `user_id="default"` everywhere

```python
DB_PATH  # env FINALLY_DB_PATH, default <repo>/db/finally.db (container: /app/db/finally.db)
init_db(path: str | None = None) -> None    # create tables + seed if missing (idempotent)
get_connection() -> sqlite3.Connection      # row_factory = sqlite3.Row

# users_profile
get_cash(user_id="default") -> float
set_cash(cash: float, user_id="default") -> None
# watchlist
get_watchlist(user_id="default") -> list[str]          # ordered by added_at
add_watchlist_ticker(ticker, user_id="default") -> bool     # False if already present
remove_watchlist_ticker(ticker, user_id="default") -> bool  # False if absent
# positions
get_positions(user_id="default") -> list[dict]  # {ticker, quantity, avg_cost, updated_at}
get_position(ticker, user_id="default") -> dict | None
upsert_position(ticker, quantity, avg_cost, user_id="default") -> None  # quantity 0 => delete row
# trades
record_trade(ticker, side, quantity, price, user_id="default") -> dict
get_trades(user_id="default", limit=50) -> list[dict]
# snapshots
record_snapshot(total_value, user_id="default") -> None
get_snapshots(user_id="default", limit=1000) -> list[dict]  # {total_value, recorded_at}, oldest first
# chat
add_chat_message(role, content, actions: dict | list | None = None, user_id="default") -> dict
get_chat_messages(user_id="default", limit=20) -> list[dict]  # oldest first, actions decoded
```
Trade execution must update cash + position + trade log atomically: also expose
`execute_trade_tx(ticker, side, quantity, price, user_id="default") -> dict` that does all three in one
transaction (raises `ValueError` on insufficient cash/shares). Timestamps: ISO 8601 UTC.

### `app.llm` (llm-engineer) — LiteLLM → OpenRouter → Cerebras (see `cerebras` skill)

```python
class TradeAction(BaseModel): ticker: str; side: Literal["buy","sell"]; quantity: float
class WatchlistChange(BaseModel): ticker: str; action: Literal["add","remove"]
class LLMResponse(BaseModel): message: str; trades: list[TradeAction] = []; watchlist_changes: list[WatchlistChange] = []

build_messages(context: dict, history: list[dict], user_message: str) -> list[dict]
get_llm_response(context: dict, history: list[dict], user_message: str) -> LLMResponse
```
- `context` = the `GET /api/portfolio` response plus `"watchlist": [{ticker, price}]`.
- `history` = `app.db.get_chat_messages()` output.
- `LLM_MOCK=true` → deterministic mock, no network. Mock rules (E2E tests depend on these):
  - message contains `buy` + a ticker + number (e.g. "buy 5 AAPL") → that trade, message `"Buying 5 AAPL."`
  - `sell N TICKER` → sell trade
  - `watch TICKER` → add to watchlist; `unwatch TICKER` → remove
  - otherwise → `LLMResponse(message="Mock response: I can help with your portfolio.")`
- Malformed LLM output → return `LLMResponse(message="Sorry, I could not process that request.")`; never raise to the route.
- The LLM module does NOT execute anything; `backend-api` executes actions.

### `app.services` / `app.api` / `app.main` (backend-api)

- `app/main.py`: FastAPI app with lifespan: `init_db()`, start market source with watchlist tickers,
  snapshot background task every 30s, stop on shutdown. Mounts `create_stream_router(cache)`.
  Serves static frontend from env `STATIC_DIR` (default `backend/static`) with `html=True`, mounted LAST,
  only if the dir exists. Loads `.env` from repo root (python-dotenv).
- Run locally: `cd backend && uv run uvicorn app.main:app --port 8000`.

## REST API (backend-api ↔ frontend ↔ integration-tester)

All JSON. Errors: HTTP 400 `{"detail": "<message>"}` (404 for unknown watchlist ticker on delete).

`GET /api/health` → `{"status": "ok"}`

`GET /api/portfolio` →
```json
{"cash": 10000.0, "total_value": 10000.0, "positions_value": 0.0, "unrealized_pnl": 0.0,
 "positions": [{"ticker":"AAPL","quantity":5,"avg_cost":190.1,"current_price":191.0,
                "market_value":955.0,"unrealized_pnl":4.5,"pnl_percent":0.47}]}
```
`POST /api/portfolio/trade` body `{"ticker":"AAPL","quantity":5,"side":"buy"}` →
`{"trade": {id,ticker,side,quantity,price,executed_at}, "portfolio": <GET /api/portfolio shape>}`.
Ticker must have a live price in the cache (else 400). Records a snapshot after each trade.

`GET /api/portfolio/history` → `[{"total_value": 10000.0, "recorded_at": "..."}]`

`GET /api/watchlist` → `[{"ticker":"AAPL","price":190.5,"previous_price":190.4,"change_percent":0.05,"day_change_percent":0.3,"direction":"up"}]` (price fields null until first tick)
`POST /api/watchlist` body `{"ticker":"PYPL"}` → 201 `{"ticker":"PYPL"}` (adds to market source too)
`DELETE /api/watchlist/{ticker}` → `{"ticker":"PYPL"}`

`POST /api/chat` body `{"message":"..."}` →
```json
{"message": "...",
 "trades": [{"ticker":"AAPL","side":"buy","quantity":5,"status":"executed","price":190.5,"error":null}],
 "watchlist_changes": [{"ticker":"PYPL","action":"add","status":"executed","error":null}]}
```
Failed actions have `"status":"failed"` and an `error` string. Both messages are stored in `chat_messages`.

`GET /api/chat/history` → `[{"role","content","actions","created_at"}]` (extra endpoint, for reloads)

`GET /api/stream/prices` → SSE (existing). Each event: `data: {"AAPL": {ticker, price, previous_price,
timestamp, change, change_percent, direction, prev_close, day_change_percent}, ...}`

## Frontend Seams (frontend-engineer ↔ devops ↔ integration-tester)

- Next.js static export (`output: 'export'`), build output in `frontend/out/`. Dev: `npm run dev` with
  `rewrites` is not available under export — use a `NEXT_PUBLIC_API_BASE` env (default `""`) for dev.
- Docker copies `frontend/out/` → `/app/backend/static`; sets `STATIC_DIR=/app/backend/static`.
- `data-testid` attributes (E2E tests rely on these):
  `header-total-value`, `header-cash`, `connection-status` (with `data-status="connected|reconnecting|disconnected"`),
  `watchlist-row-{TICKER}`, `watchlist-price-{TICKER}`, `watchlist-add-input`, `watchlist-add-button`,
  `watchlist-remove-{TICKER}`, `main-chart`, `heatmap`, `pnl-chart`, `positions-table`,
  `position-row-{TICKER}`, `trade-ticker-input`, `trade-quantity-input`, `trade-buy-button`,
  `trade-sell-button`, `trade-error`, `chat-panel`, `chat-input`, `chat-send-button`,
  `chat-message` (each message), `chat-loading`, `chat-action` (each inline trade/watchlist confirmation).

## Docker (devops-engineer)

- Image name `finally`, container name `finally`, volume `finally-data:/app/db`, port 8000, `--env-file .env`.
- Container env: `FINALLY_DB_PATH=/app/db/finally.db`, `STATIC_DIR=/app/backend/static`.
- `test/docker-compose.test.yml` (owned by integration-tester) builds from the root `Dockerfile` with `LLM_MOCK=true`.

## Working Rules

- Read `~/.claude/CLAUDE.md` + project `CLAUDE.md`: simple, incremental, validate each step, `uv run` / `uv add` only.
- Unit tests for everything you own; run them before reporting done.
- Integration issues go in `planning/ISSUES.md` (owner, repro, expected/actual) and a SendMessage to the owner.
- When done with a milestone, message `team-lead` with a short status.
