#!/usr/bin/env bash
# Idempotent Cloud Agent bootstrap for the Buttons Bebe helpdesk.
# Creates a repo-root .venv and installs every Python component.
# The inbox review server and helpdesk-agent CLI run from stdlib only; the
# webhook/processor/tools/kb stacks need their pinned dependencies.
set -euo pipefail

cd "$(dirname "$0")/.."

# The base image ships CPython without the venv seed package; add it once.
if ! python3 -c "import ensurepip" >/dev/null 2>&1; then
  sudo apt-get update -y
  sudo apt-get install -y python3.12-venv
fi

if [ ! -x ".venv/bin/python" ]; then
  python3 -m venv .venv
fi

# shellcheck disable=SC1091
. .venv/bin/activate
python -m pip install --upgrade pip

# Light services first, then the heavier KB embedding/search stack.
pip install -e ./webhook -e ./processor -r tools/requirements.txt
pip install -r kb/requirements.txt

echo "install: dependencies ready in .venv"
