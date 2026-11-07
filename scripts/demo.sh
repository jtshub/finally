#!/usr/bin/env bash
# Launch the FinAlly live terminal demo (simulated market data, no API keys needed).
# Usage: scripts/demo.sh        (run from anywhere; Ctrl+C to exit early)
set -euo pipefail

if ! command -v uv >/dev/null 2>&1; then
  echo "uv is required. Install it from https://docs.astral.sh/uv/getting-started/installation/" >&2
  exit 1
fi

cd "$(dirname "${BASH_SOURCE[0]}")/../backend"
uv sync --quiet
exec uv run market_data_demo.py
