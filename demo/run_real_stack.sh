#!/usr/bin/env bash
# Start the real app against only the Cute Things localhost demo boundary.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

env_file="demo/.env"
if [ ! -f "$env_file" ]; then
  env_file="demo/.env.example"
fi

python3 demo/verify_config.py "$env_file"

# Remove all inherited client-integration values, including legacy spellings,
# before exporting the statically validated demo profile. Values are never read
# or printed.
while IFS='=' read -r key _value; do
  case "$key" in
    SHOPIFY_*|GORGIAS_*|REDO_*|WHATSAPP_*|WA_*|TWILIO_*|FEEDBACK_*)
      unset "$key"
      ;;
  esac
done < <(env)

set -a
# shellcheck disable=SC1090
. "$env_file"
set +a

export DEMO_MODE=1
export PYTHONPATH="$ROOT_DIR/webhook/src"

mkdir -p demo/data/kb/learned webhook/data

fake_pid=""
webhook_pid=""
processor_pid=""
console_pid=""
cleanup() {
  for pid in "$console_pid" "$processor_pid" "$webhook_pid" "$fake_pid"; do
    if [ -n "$pid" ]; then
      kill "$pid" 2>/dev/null || true
    fi
  done
}
trap cleanup EXIT INT TERM

bash demo/run_fake_services.sh &
fake_pid=$!

webhook/.venv/bin/python -m uvicorn bb_webhook.app:app \
  --host 127.0.0.1 --port 8100 &
webhook_pid=$!

ready=0
for _attempt in $(seq 1 100); do
  if python3 -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8100/ready', timeout=1)" >/dev/null 2>&1; then
    ready=1
    break
  fi
  sleep 0.1
done
if [ "$ready" -ne 1 ]; then
  echo "Demo webhook did not become ready" >&2
  exit 1
fi

processor/.venv/bin/python processor/orchestrator.py &
processor_pid=$!

python3 demo/serve_console.py &
console_pid=$!

echo "Cute Things real-app demo is running at http://127.0.0.1:8101/"
echo "All integrations are localhost simulators. Press Ctrl-C to stop."

while kill -0 "$fake_pid" "$webhook_pid" "$processor_pid" "$console_pid" 2>/dev/null; do
  sleep 1
done

echo "A demo process exited unexpectedly; stopping the stack" >&2
exit 1
