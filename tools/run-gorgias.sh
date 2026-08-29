#!/usr/bin/env bash
# Launcher for the Gorgias MCP tool. Resolves paths from this script so a
# buyer can run it from any install root.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
if [[ -x "$ROOT/tools/.venv/bin/python" ]]; then
  exec "$ROOT/tools/.venv/bin/python" "$ROOT/tools/gorgias_mcp.py"
fi
exec python3 "$ROOT/tools/gorgias_mcp.py"
