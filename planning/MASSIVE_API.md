# Massive API (formerly Polygon.io) — Stock Prices Reference

Reference for retrieving **real-time / delayed** and **end-of-day (EOD)** stock prices for
multiple tickers from Massive. Researched 2026-11-07 against the official docs at
`massive.com/docs` and the source of the `massive` Python SDK (v2.9.1 latest; v2.2.0 pinned
in `backend/uv.lock` — the endpoints and models used below are the same in both).

---

## 1. Key Facts

| Item | Value |
|---|---|
| Base URL | `https://api.massive.com` (legacy `https://api.polygon.io` still works) |
| Auth | API key. SDK sends `Authorization: Bearer <key>`. Raw HTTP may also use `?apiKey=<key>` |
| Key env var | `MASSIVE_API_KEY` (the SDK reads it automatically if `api_key` is not passed) |
| Python SDK | `massive` on PyPI (`uv add massive`), import `from massive import RESTClient` |
| SDK style | **Synchronous** (urllib3). Wrap calls in `asyncio.to_thread()` inside FastAPI |
| Errors | Non-200 → `massive.exceptions.BadResponse` (body text in message). Missing key → `AuthError` |
| Tickers | Case-sensitive — always upper-case (`AAPL`, not `aapl`) |

## 2. Plans — What You Can Actually Call

From `massive.com/stocks` (individual, non-professional plans):

| Plan | Price/mo | Rate limit | Data recency | History | Snapshots | Trades | Quotes |
|---|---|---|---|---|---|---|---|
| **Basic** | $0 | **5 calls/min** | **End-of-day** | 2 yrs | **No** | No | No |
| Starter | $29 | Unlimited | 15-min delayed | 5 yrs | Yes | No | No |
| Developer | $79 | Unlimited | 15-min delayed | 10 yrs | Yes | Yes | No |
| Advanced | $199 | Unlimited | Real-time | 20+ yrs | Yes | Yes | Yes |

Consequences for FinAlly:

- **Free (Basic) keys cannot call any snapshot endpoint.** Only aggregate/EOD endpoints
  (§4) work, and prices only change once per day.
- **Starter/Developer snapshots omit fields.** Docs: `lastTrade` is "only returned if your
  current plan includes trades" and `lastQuote` "only if your plan includes quotes". On Starter
  there is no `lastTrade`, so the price must come from `min.c` / `day.c` instead.
- "Unlimited" plans still deserve a sane poll interval (2–5 s); exceeding Basic returns HTTP 429.

## 3. Live Prices for Multiple Tickers (Snapshots)

### 3.1 Full Market Snapshot — the one we use

`GET /v2/snapshot/locale/us/markets/stocks/tickers?tickers=AAPL,MSFT,...`

One request returns the latest data for every listed ticker. Plans: Starter+.

| Query param | Notes |
|---|---|
| `tickers` | Comma-separated, case-sensitive. Omit → **entire market (10k+ tickers)** — always pass it |
| `include_otc` | Default `false` |

Response (trimmed, from docs):

```json
{
  "status": "OK",
  "count": 1,
  "tickers": [
    {
      "ticker": "AAPL",
      "todaysChange": 0.98,
      "todaysChangePerc": 0.82,
      "updated": 1605195918306274000,
      "day":     {"o": 119.62, "h": 120.53, "l": 118.81, "c": 120.4229, "v": 28727868, "vw": 119.725},
      "prevDay": {"o": 117.19, "h": 119.63, "l": 116.44, "c": 119.49,   "v": 110597265, "vw": 118.4998},
      "min":     {"o": 120.43, "h": 120.47, "l": 120.42, "c": 120.47, "v": 5000, "av": 28727868, "n": 10, "t": 1605195900000},
      "lastTrade": {"p": 120.47, "s": 236, "x": 10, "c": [14, 41], "t": 1605195918306274000},
      "lastQuote": {"P": 120.47, "S": 4, "p": 120.46, "s": 8, "t": 1605195918507251700}
    }
  ]
}
```

Field meanings: `day` = today's session bar so far, `prevDay` = previous session's bar
(`prevDay.c` = previous close), `min` = latest minute bar, `lastTrade.p` = last trade price,
`lastQuote.p/P` = bid/ask price, `s/S` = bid/ask size.

**Timestamp units differ per field (the docs don't label them; inferred from digit counts and
confirmed in the SDK):**

| Field | Unit | To Unix seconds |
|---|---|---|
| `updated`, `lastTrade.t`, `lastQuote.t` | **nanoseconds** | `/ 1e9` |
| `min.t`, all aggregate `t` | milliseconds | `/ 1e3` |

Data lifecycle: snapshot data is cleared daily at ~3:30 AM ET and repopulates from ~4:00 AM ET
as exchange data arrives. Outside market hours you get the last values of the most recent
session (fine for us — prices simply stop changing).

SDK example:

```python
from massive import RESTClient
from massive.rest.models import SnapshotMarketType

client = RESTClient()  # reads MASSIVE_API_KEY

snapshots = client.get_snapshot_all(
    market_type=SnapshotMarketType.STOCKS,
    tickers=["AAPL", "MSFT", "NVDA"],  # list is joined with commas by the SDK
)
for s in snapshots:  # list[TickerSnapshot]
    price = (
        (s.last_trade and s.last_trade.price)   # Developer+
        or (s.min and s.min.close)              # Starter: latest minute bar
        or (s.day and s.day.close)
    )
    prev_close = s.prev_day.close if s.prev_day else None
    ts = s.updated / 1e9 if s.updated else None  # ns → s
    print(s.ticker, price, prev_close, s.todays_change_percent, ts)
```

SDK model attribute names (`massive.rest.models.TickerSnapshot`) — note they are **not** the
JSON keys:

| JSON | SDK attribute |
|---|---|
| `lastTrade.p` / `lastTrade.t` | `last_trade.price` / `last_trade.sip_timestamp` (ns) |
| `lastQuote` | `last_quote` (`bid_price`, `ask_price`, ...) |
| `min.c` / `min.t` | `min.close` / `min.timestamp` (ms) |
| `day.c`, `prevDay.c` | `day.close`, `prev_day.close` |
| `todaysChange`, `todaysChangePerc` | `todays_change`, `todays_change_percent` |
| `updated` | `updated` (ns) |

> ⚠️ `LastTrade` has **no `timestamp` attribute** — it is `sip_timestamp` (nanoseconds).
> Verified against SDK 2.2.0: `hasattr(snap.last_trade, "timestamp") is False`.

### 3.2 Single Ticker Snapshot

`GET /v2/snapshot/locale/us/markets/stocks/tickers/{ticker}` — same fields, wrapped in
`"ticker": {...}` rather than a `"tickers": [...]` array. Plans: Starter+.

```python
snap = client.get_snapshot_ticker(SnapshotMarketType.STOCKS, "AAPL")
```

Useful to validate a single newly added ticker; for polling, always prefer the multi-ticker call.

### 3.3 Unified Snapshot (v3, multi-asset)

`GET /v3/snapshot?ticker.any_of=AAPL,MSFT&limit=250` — stocks, options, FX, crypto, indices.
Max 250 tickers, paginated (`next_url`). Plans: Starter+. Per-ticker unknown symbols come back
inline as `{"ticker": "XYZ", "error": "NOT_FOUND", "message": "Ticker not found."}` rather than
failing the request — handy for validating user-entered tickers.

```python
for s in client.list_universal_snapshots(ticker_any_of=["AAPL", "MSFT"], limit=250):
    if s.error:
        print(s.ticker, s.error)
    else:
        print(s.ticker, s.session.close, s.session.previous_close, s.market_status)
```

Fields of interest: `session.{open,high,low,close,change,change_percent,previous_close,volume}`,
`last_trade.{price,last_updated(ns)}`, `market_status` (`open`, `closed`, `early_trading`,
`late_trading`). We do not need it today; v2 full snapshot is simpler for a fixed stock list.

### 3.4 Last Trade / Last Quote (single ticker)

`GET /v2/last/trade/{ticker}` (Developer+), `GET /v2/last/nbbo/{ticker}` (Advanced). One call
per ticker — **do not use for polling a watchlist**; the snapshot covers all tickers in one call.

```python
t = client.get_last_trade("AAPL")      # t.price, t.sip_timestamp (ns)
q = client.get_last_quote("AAPL")      # q.bid_price, q.ask_price
```

## 4. End-of-Day Prices (all plans, including free Basic)

All return `t` in **milliseconds**. All accept `adjusted` (default `true` = split-adjusted).

### 4.1 Daily Market Summary (grouped daily) — EOD for every ticker in ONE call

`GET /v2/aggs/grouped/locale/us/market/stocks/{YYYY-MM-DD}`

Returns OHLCV for every US stock on that trading day. Best option for the free tier: one call
covers any number of watchlist tickers. Non-trading days return an empty `results` list.

```json
{"status": "OK", "adjusted": true, "resultsCount": 2, "results": [
  {"T": "AAPL", "o": 324.66, "h": 326.2, "l": 322.3, "c": 325.12, "v": 26122646, "vw": 324.1, "n": 412000, "t": 1673298000000}
]}
```

```python
from datetime import date, timedelta

def latest_eod_closes(client: RESTClient, tickers: set[str]) -> dict[str, float]:
    """Close prices from the most recent trading day (walks back over weekends/holidays)."""
    day = date.today() - timedelta(days=1)
    for _ in range(7):
        bars = client.get_grouped_daily_aggs(day.isoformat())
        if bars:
            return {b.ticker: b.close for b in bars if b.ticker in tickers}
        day -= timedelta(days=1)
    return {}
```

(Each loop iteration is one API call — mind the 5/min Basic limit.)

### 4.2 Previous Day Bar (one ticker)

`GET /v2/aggs/ticker/{ticker}/prev` — previous session's OHLCV. Returns a **list** with one item.

```python
[bar] = client.get_previous_close_agg("AAPL")
print(bar.close, bar.timestamp)  # timestamp in ms
```

### 4.3 Daily Ticker Summary (open/close for a date)

`GET /v1/open-close/{ticker}/{YYYY-MM-DD}` — flat object with `open, high, low, close, volume,
preMarket, afterHours, symbol, from`. Note the key is `symbol`, not `ticker`.

```python
oc = client.get_daily_open_close_agg("AAPL", "2026-11-06")
print(oc.open, oc.close, oc.pre_market, oc.after_hours)
```

### 4.4 Custom Bars (historical range)

`GET /v2/aggs/ticker/{ticker}/range/{multiplier}/{timespan}/{from}/{to}` — e.g. daily bars for
a chart. `timespan`: `minute|hour|day|week|month|quarter|year`. `from`/`to` are inclusive
dates or ms timestamps. `limit` default 5000, max 50000. Paginates via `next_url`.

```python
bars = client.get_aggs("AAPL", 1, "day", "2026-10-01", "2026-11-06")
closes = [(b.timestamp / 1000, b.close) for b in bars]

# list_aggs() is the paginating iterator version (follows next_url automatically)
for b in client.list_aggs("AAPL", 5, "minute", "2026-11-06", "2026-11-06", limit=50000):
    ...
```

## 5. Raw HTTP (no SDK)

Useful for debugging with curl, or to see exact JSON:

```bash
curl -s -H "Authorization: Bearer $MASSIVE_API_KEY" \
  "https://api.massive.com/v2/snapshot/locale/us/markets/stocks/tickers?tickers=AAPL,MSFT" | jq

curl -s "https://api.massive.com/v2/aggs/grouped/locale/us/market/stocks/2026-11-06?apiKey=$MASSIVE_API_KEY" | jq '.results[] | select(.T=="AAPL")'
```

```python
import httpx

async def fetch_snapshots(api_key: str, tickers: list[str]) -> list[dict]:
    async with httpx.AsyncClient(base_url="https://api.massive.com", timeout=10) as http:
        r = await http.get(
            "/v2/snapshot/locale/us/markets/stocks/tickers",
            params={"tickers": ",".join(tickers)},
            headers={"Authorization": f"Bearer {api_key}"},
        )
        r.raise_for_status()
        return r.json().get("tickers", [])
```

We use the SDK (already a dependency); `httpx` is shown only as a reference.

## 6. Using the SDK from asyncio / FastAPI

The client is synchronous and thread-safe (pooled urllib3). Create one per process and call it
via a worker thread so the event loop is never blocked:

```python
import asyncio
from massive import RESTClient
from massive.rest.models import SnapshotMarketType

client = RESTClient(api_key=key)  # defaults: connect/read timeout 10s, retries=3

snaps = await asyncio.to_thread(
    client.get_snapshot_all, SnapshotMarketType.STOCKS, tickers
)
```

## 7. Errors and Gotchas

| Situation | Behaviour |
|---|---|
| Bad/missing key | HTTP 401 → `BadResponse` |
| Endpoint not in plan (e.g. snapshot on Basic) | HTTP 403, `"status": "NOT_AUTHORIZED"` → `BadResponse` (body format is from prior Polygon behaviour; not verified live — no key available during research) |
| Rate limit exceeded | HTTP 429 → `BadResponse` after SDK retries |
| Unknown ticker in snapshot `tickers=` | Simply absent from `tickers[]` — no error |
| Unknown ticker in `/v3/snapshot` | Inline `error: "NOT_FOUND"` entry |
| Market closed | Snapshot returns last session values; prices stop changing |
| Field absent for plan | SDK attribute is `None` (e.g. `last_trade` on Starter) |
| Timestamps | Snapshot `updated`/`lastTrade.t` = ns; aggregates `t` = ms |

## Sources

- [Full Market Snapshot](https://massive.com/docs/rest/stocks/snapshots/full-market-snapshot)
- [Single Ticker Snapshot](https://massive.com/docs/rest/stocks/snapshots/single-ticker-snapshot)
- [Unified Snapshot](https://massive.com/docs/rest/stocks/snapshots/unified-snapshot)
- [Previous Day Bar](https://massive.com/docs/rest/stocks/aggregates/previous-day-bar)
- [Daily Market Summary](https://massive.com/docs/rest/stocks/aggregates/daily-market-summary)
- [Daily Ticker Summary](https://massive.com/docs/rest/stocks/aggregates/daily-ticker-summary)
- [Custom Bars](https://massive.com/docs/rest/stocks/aggregates/custom-bars)
- [Stocks plans](https://massive.com/stocks), [Pricing](https://massive.com/pricing)
- [Max tickers in a snapshot (KB)](https://massive.com/knowledge-base/article/what-is-the-max-number-of-tickers-i-can-pass-through-massives-snapshot)
- `massive` SDK source: `massive/rest/snapshot.py`, `aggs.py`, `trades.py`, `models/*.py` ([PyPI](https://pypi.org/project/massive/))
