# FinAlly — AI Trading Workstation

An AI-powered trading workstation that streams live market data, simulates portfolio trading, and includes an LLM chat assistant that can analyze positions and execute trades in natural language.

Built by coding agents as a capstone project for an agentic AI coding course.

## Status

- **Market data backend** — complete (GBM simulator + optional Massive/Polygon.io feed, SSE streaming). See `planning/MARKET_DATA_SUMMARY.md`.
- **Portfolio, chat, frontend, Docker packaging** — not yet built.

## Planned Architecture

Single container on port 8000:

- **Frontend**: Next.js static export, TypeScript, Tailwind CSS
- **Backend**: FastAPI (Python, `uv`) with SSE price streaming
- **Database**: SQLite
- **AI**: LiteLLM → OpenRouter (Cerebras inference)
- **Market data**: built-in simulator by default, Massive API when `MASSIVE_API_KEY` is set

## Getting Started (backend)

```bash
cd backend
uv sync --dev
uv run pytest                  # run tests
uv run market_data_demo.py     # live terminal demo of the simulator
```

### Quick demo

From the repo root (requires [uv](https://docs.astral.sh/uv/)):

```bash
bash scripts/demo.sh
```

This opens a live terminal dashboard of the 10 default tickers with simulated prices, sparklines and a "notable moves" log. It runs for 60 seconds (or until Ctrl+C) and then prints a session summary. No API keys needed.

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `OPENROUTER_API_KEY` | For AI chat | OpenRouter API key |
| `MASSIVE_API_KEY` | No | Real market data; omit to use the simulator |
| `LLM_MOCK` | No | `true` for deterministic mock LLM responses |

## Project Structure

```
finally/
├── backend/     # FastAPI uv project (market data in app/market/)
├── planning/    # Project docs
└── independent-reviewer/
```

## License

See [LICENSE](LICENSE).
