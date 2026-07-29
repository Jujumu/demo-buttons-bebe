#!/usr/bin/env bash
# run.sh — start the job processor
# Usage: ./run.sh
set -euo pipefail
cd "$(dirname "$0")"

export PATH="$HOME/.local/bin:$PATH"

# Activate venv if exists, otherwise create it
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    uv venv
    echo "Installing dependencies..."
    uv pip install -e .
fi

# Ensure the shared .env exists. Since the 2026-07-08 consolidation both the
# processor and the webhook read the SAME file at the project root — see
# processor/config.py. webhook/.env is legacy; fall back to it only if the
# consolidated file is missing, so an un-migrated VPS still starts.
ENV_FILE="../.env"
if [ ! -f "$ENV_FILE" ]; then
    if [ -f "../webhook/.env" ]; then
        ENV_FILE="../webhook/.env"
        echo "WARNING: using legacy ../webhook/.env — see deploy/ENV-CONSOLIDATION-RUNBOOK.md"
    else
        echo "ERROR: no .env found at ../.env (or the legacy ../webhook/.env)."
        exit 1
    fi
fi

echo "Starting job processor..."
echo "  Config file:   $ENV_FILE"
echo "  Poll interval: $(grep -E '^PROCESSOR_POLL_INTERVAL=' "$ENV_FILE" 2>/dev/null | cut -d= -f2 || echo '2.0s (default)')"

exec uv run python -m orchestrator