#!/usr/bin/env bash
# Offline release gate for the live Buttons Bebe source tree.
#
# This script deliberately does not install dependencies, start services, call
# external APIs, or mutate a VPS. CI installs the declared manifests first;
# local callers should point PYTHON/PROCESSOR_PYTHON at an already prepared env.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="${PYTHON:-python3}"
PROCESSOR_PYTHON="${PROCESSOR_PYTHON:-$PYTHON}"

fail() {
  echo "release gate failed: $*" >&2
  exit 1
}

cd "$ROOT_DIR"

for required in \
  "processor/pyproject.toml" \
  "processor/uv.lock" \
  "webhook/pyproject.toml" \
  "webhook/uv.lock" \
  "kb/requirements.txt" \
  "tools/requirements.txt" \
  "whatsapp-connect/package.json" \
  "whatsapp-connect/package-lock.json"; do
  [[ -f "$required" ]] || fail "missing dependency manifest: $required"
done

"$PYTHON" - <<'PY'
from pathlib import Path
import ast
import json

roots = [Path("feedback"), Path("kb"), Path("processor"), Path("testing"), Path("tools"), Path("webhook"), Path("deploy")]
for root in roots:
    for path in root.rglob("*.py"):
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

scenarios = json.loads(Path("testing/scenarios.json").read_text(encoding="utf-8"))
if len(scenarios) != 48:
    raise SystemExit(f"testing/scenarios.json must hold 48 scenarios, found {len(scenarios)}")
ids = [s.get("id") for s in scenarios]
if len(set(ids)) != len(ids):
    raise SystemExit("testing/scenarios.json has duplicate scenario ids")

package = json.loads(Path("whatsapp-connect/package.json").read_text(encoding="utf-8"))
lock = json.loads(Path("whatsapp-connect/package-lock.json").read_text(encoding="utf-8"))
if package.get("name") != lock.get("name") or package.get("version") != lock.get("version"):
    raise SystemExit("WhatsApp package.json and package-lock.json metadata differ")
if package.get("dependencies") != lock.get("packages", {}).get("", {}).get("dependencies"):
    raise SystemExit("WhatsApp dependency lock does not match package.json")
PY

# Tracked AND untracked. `git ls-files '*.sh'` alone skipped a new script
# until it was staged - exactly when a local pre-commit run is most useful -
# and silently checked nothing at all outside a git checkout, while the gate
# still printed "release gate passed: ... syntax ...".
shell_scripts=()
while IFS= read -r -d '' script; do
  [[ -f "$script" ]] || continue
  shell_scripts+=("$script")
done < <(git ls-files -z --cached --others --exclude-standard '*.sh') \
  || fail "could not list shell scripts (not a git checkout?)"
[[ ${#shell_scripts[@]} -gt 0 ]] || fail "no shell scripts found - the listing is broken"
echo "release gate: checking ${#shell_scripts[@]} shell scripts"
for script in "${shell_scripts[@]}"; do
  bash -n "$script"
done

# rg exits 0 on a match, 1 on none, 2+ on error - and it is in none of the
# eight manifests above. `if rg ...` treated both "not installed" (127) and
# "bad path" (2) as "clean", so the check could pass without ever running.
command -v rg >/dev/null 2>&1 || fail "ripgrep (rg) is required by this gate"
set +e
rg -n -i 'twilio|twilio_' processor webhook tools kb whatsapp-connect \
    --glob '*.py' --glob '*.js' --glob '*.sh' --glob '!verify_release.sh'
rg_status=$?
set -e
case "$rg_status" in
  0) fail "active Twilio reference found" ;;
  1) ;;  # clean
  *) fail "ripgrep failed with status $rg_status - the Twilio check did not run" ;;
esac

# The feedback and KB suites already replace optional network/vector modules in
# their tests. Keep the requests stub explicit so this gate remains offline.
"$PYTHON" -c 'import sys,types,unittest; requests=types.ModuleType("requests"); requests.get=lambda *a,**k: None; requests.post=lambda *a,**k: None; sys.modules["requests"]=requests; names=["feedback.tests.test_all","feedback.tests.test_retirement"]; suite=unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromName(n) for n in names); result=unittest.TextTestRunner(verbosity=1).run(suite); raise SystemExit(not result.wasSuccessful())'
"$PYTHON" -m unittest discover -s kb/tests -v
"$PYTHON" -m unittest discover -s deploy/tests -v
"$PYTHON" -m unittest tools.test_tool_contracts -v
PYTHONPATH="$ROOT_DIR/webhook/src${PYTHONPATH:+:$PYTHONPATH}" \
  "$PYTHON" -m unittest discover -s webhook -p 'test_notifications.py' -v
if "$PYTHON" -c 'import aiosqlite' >/dev/null 2>&1; then
  PYTHONPATH="$ROOT_DIR/webhook/src${PYTHONPATH:+:$PYTHONPATH}" \
    "$PYTHON" -m unittest discover -s webhook -p 'test_notification_api.py' -v
fi
# Every processor/test_*.py runs, discovered rather than listed, so a new test
# file cannot be added without CI picking it up - and so each task in the Fable
# port does not have to edit this same line (which conflicts on merge).
# test_e2e.py is excluded: it is a live diagnostic script against a running VPS,
# not an offline unit test.
processor_tests=()
for _test in processor/test_*.py; do
  [[ -e "$_test" ]] || continue
  _name="$(basename "$_test" .py)"
  # Live diagnostics opt OUT with a marker line rather than by filename, so
  # renaming or adding one cannot silently pull a VPS-hitting script into the
  # offline gate.
  grep -q '^# offline-gate: skip' "$_test" && continue
  processor_tests+=("processor.$_name")
done
if [[ ${#processor_tests[@]} -eq 0 ]]; then
  fail "no processor test modules found - the discovery glob is wrong"
fi
echo "release gate: processor tests -> ${processor_tests[*]}"
"$PROCESSOR_PYTHON" -m unittest "${processor_tests[@]}" -v

node --check whatsapp-connect/server.js
node --test whatsapp-connect/test/security.test.js
node --check kb-admin/server.js
node --test kb-admin/test/server.test.js

echo "release gate passed: manifests, syntax, offline tests, KB admin safety, WhatsApp auth, and no-Twilio check"
