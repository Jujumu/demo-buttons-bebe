#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
HOST="${INBOX_HOST:-127.0.0.1}"
PORT="${INBOX_PORT:-8766}"
export SHOPIFY_MUTATIONS_ENABLED="${SHOPIFY_MUTATIONS_ENABLED:-0}"
export PYTHONUNBUFFERED=1
exec python3 console-src/inbox/review_server.py --host "$HOST" --port "$PORT"
