#!/usr/bin/env bash
# Start all local, fixture-backed dependency simulators for the Cute Things demo.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

kb_pid=""
redo_pid=""
wa_pid=""
gorgias_mcp_pid=""
gorgias_rest_pid=""
cleanup() {
  if [ -n "$kb_pid" ]; then kill "$kb_pid" 2>/dev/null || true; fi
  if [ -n "$redo_pid" ]; then kill "$redo_pid" 2>/dev/null || true; fi
  if [ -n "$wa_pid" ]; then kill "$wa_pid" 2>/dev/null || true; fi
  if [ -n "$gorgias_mcp_pid" ]; then kill "$gorgias_mcp_pid" 2>/dev/null || true; fi
  if [ -n "$gorgias_rest_pid" ]; then kill "$gorgias_rest_pid" 2>/dev/null || true; fi
}
trap cleanup EXIT INT TERM

echo "Starting fake Cute Things KB on http://127.0.0.1:8177/mcp"
KB_MCP_HOST=127.0.0.1 \
KB_MCP_PORT=8177 \
KB_MCP_TRANSPORT=streamable-http \
DEMO_KB_FIXTURES=demo/fixtures/kb.json \
python3 demo/fake_kb_mcp.py &
kb_pid=$!

echo "Starting fake Cute Things Redo on http://127.0.0.1:8178/mcp"
REDO_MCP_HOST=127.0.0.1 \
REDO_MCP_PORT=8178 \
REDO_MCP_TRANSPORT=streamable-http \
DEMO_REDO_FIXTURES=demo/fixtures/redo.json \
python3 demo/fake_redo_mcp.py &
redo_pid=$!

echo "Starting fake WhatsApp on http://127.0.0.1:8185"
DEMO_WHATSAPP_PORT=8185 \
DEMO_WHATSAPP_FIXTURES=demo/fixtures/whatsapp.json \
DEMO_WA_SEND_SECRET="${DEMO_WA_SEND_SECRET:-demo-only-whatsapp-send-secret}" \
DEMO_WA_OUTBOX=demo/data/cute-things-demo-whatsapp-outbox.jsonl \
python3 demo/fake_whatsapp.py &
wa_pid=$!

echo "Starting fake Cute Things Gorgias MCP on http://127.0.0.1:8179/mcp"
GORGIAS_MCP_HOST=127.0.0.1 \
GORGIAS_MCP_PORT=8179 \
GORGIAS_MCP_TRANSPORT=streamable-http \
DEMO_GORGIAS_FIXTURES=demo/fixtures/gorgias.json \
python3 demo/fake_gorgias_mcp.py &
gorgias_mcp_pid=$!

echo "Starting fake Gorgias REST sink on http://127.0.0.1:8190"
DEMO_GORGIAS_PORT=8190 \
DEMO_GORGIAS_FIXTURES=demo/fixtures/gorgias.json \
DEMO_GORGIAS_ACTION_LOG=demo/data/cute-things-demo-gorgias-actions.jsonl \
python3 demo/fake_gorgias_rest.py &
gorgias_rest_pid=$!

echo "All five fake dependency services are running. Press Ctrl-C to stop them."
wait "$kb_pid" "$redo_pid" "$wa_pid" "$gorgias_mcp_pid" "$gorgias_rest_pid"
