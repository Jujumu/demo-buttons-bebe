#!/usr/bin/env bash
# Launcher for the KB search connector (the "search_kb" tool for Hermes).
# Resolves paths from this script so a buyer can run it from any install root.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  exec "$ROOT/.venv/bin/python" "$ROOT/scripts/kb_mcp_server.py"
fi
exec python3 "$ROOT/scripts/kb_mcp_server.py"
