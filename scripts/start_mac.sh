#!/usr/bin/env bash
# Start the FinAlly container. Usage: scripts/start_mac.sh [--build] [--open]
set -euo pipefail

IMAGE=finally
CONTAINER=finally
VOLUME=finally-data
PORT=8000
URL="http://localhost:${PORT}"

cd "$(dirname "${BASH_SOURCE[0]}")/.."

BUILD=false
OPEN=false
for arg in "$@"; do
  case "$arg" in
    --build) BUILD=true ;;
    --open) OPEN=true ;;
    *) echo "Unknown option: $arg" >&2; exit 1 ;;
  esac
done

if $BUILD || ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
  echo "Building image '$IMAGE'..."
  docker build -t "$IMAGE" .
fi

docker rm -f "$CONTAINER" >/dev/null 2>&1 || true

ENV_ARGS=()
if [[ -f .env ]]; then
  ENV_ARGS=(--env-file .env)
else
  echo "Warning: .env not found; starting without it (LLM chat needs OPENROUTER_API_KEY)." >&2
fi

docker run -d --name "$CONTAINER" \
  -v "$VOLUME:/app/db" \
  -p "$PORT:8000" \
  ${ENV_ARGS[@]+"${ENV_ARGS[@]}"} \
  "$IMAGE" >/dev/null

echo "FinAlly is running at $URL"
if $OPEN && command -v open >/dev/null 2>&1; then
  open "$URL"
fi
