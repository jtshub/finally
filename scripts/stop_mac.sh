#!/usr/bin/env bash
# Stop and remove the FinAlly container. The data volume is kept.
set -euo pipefail

CONTAINER=finally

if docker container inspect "$CONTAINER" >/dev/null 2>&1; then
  docker rm -f "$CONTAINER" >/dev/null
  echo "Stopped FinAlly (data volume 'finally-data' kept)."
else
  echo "FinAlly is not running."
fi
