#!/usr/bin/env bash
# =============================================================================
#  verify_hermes_toolset.sh — run this on the VPS BEFORE restarting the
#  processor with the new tool allow-list (DEV-ISSUES #8).
#
#  WHY: a misspelled toolset name is silent. Hermes does not error; it just
#  loses the tool, and drafts quietly get worse with nothing in the logs.
#  This script proves the names are right before anything goes live.
#
#  READ-ONLY. It lists configuration and, only if every other check passed,
#  runs one throwaway one-shot prompt about store policy. It never writes to
#  Gorgias, Shopify, Redo or the queue, and never touches a real ticket.
#
#  USAGE:
#     bash tools/verify_hermes_toolset.sh
#     HERMES_TOOLSETS="mcp-a,mcp-b" bash tools/verify_hermes_toolset.sh
#     SKIP_LIVE=1 bash tools/verify_hermes_toolset.sh   # config checks only
# =============================================================================
set -u

TOOLSETS="$(printf '%s' "${HERMES_TOOLSETS:-mcp-buttonsbebe_kb,mcp-buttonsbebe_redo,mcp-buttonsbebe_gorgias}" | tr -d '[:space:]')"
EXPECTED_SERVERS="buttonsbebe_kb buttonsbebe_redo buttonsbebe_gorgias"
FAILED=0

say()  { printf '\n\033[1m%s\033[0m\n' "$*"; }
ok()   { printf '  \033[32mOK\033[0m   %s\n' "$*"; }
bad()  { printf '  \033[31mFAIL\033[0m %s\n' "$*"; FAILED=1; }
note() { printf '  ..   %s\n' "$*"; }

say "Toolsets the processor will pass"
note "$TOOLSETS"

# ── 1. hermes is on PATH ─────────────────────────────────────────────────
say "1. Hermes CLI"
if command -v hermes >/dev/null 2>&1; then
    ok "hermes found at $(command -v hermes)"
else
    bad "hermes not on PATH — run this as the same user as the processor (root)"
    exit 1
fi

# ── 2. the three MCP servers are registered ──────────────────────────────
say "2. Registered MCP servers (hermes mcp list)"
set +e
MCP_OUT="$(hermes mcp list 2>&1)"
MCP_STATUS=$?
set -e
printf '%s\n' "$MCP_OUT" | sed 's/^/     /'
if [ "$MCP_STATUS" -ne 0 ]; then
    bad "'hermes mcp list' exited $MCP_STATUS — cannot verify anything below"
fi
for server in $EXPECTED_SERVERS; do
    # Word-boundary match. A plain substring test would accept
    # "buttonsbebe_kb_old", or an error message that merely names the server.
    if printf '%s' "$MCP_OUT" | grep -Eq "(^|[^A-Za-z0-9_])${server}([^A-Za-z0-9_]|$)"; then
        ok "$server registered"
    else
        bad "$server NOT found in 'hermes mcp list'"
    fi
done

# ── 3. every toolset we ask for maps to a registered server ──────────────
say "3. Toolset names match the server keys"
IFS=',' read -r -a WANTED <<< "$TOOLSETS"
if [ "${#WANTED[@]}" -eq 0 ]; then
    bad "HERMES_TOOLSETS is empty — the processor would fall back to whatever config.yaml grants"
fi
for ts in "${WANTED[@]}"; do
    [ -z "$ts" ] && continue
    server="${ts#mcp-}"
    if [ "$server" = "$ts" ]; then
        note "$ts is not an mcp- toolset — skipping the server-key check"
        continue
    fi
    if printf '%s' "$MCP_OUT" | grep -Eq "(^|[^A-Za-z0-9_])${server}([^A-Za-z0-9_]|$)"; then
        ok "$ts -> server '$server'"
    else
        bad "$ts -> no server called '$server'. THIS WOULD SILENTLY LOSE THE TOOL."
    fi
done

# ── 4. terminal / file must not be granted to the CLI platform ───────────
say "4. Dangerous toolsets are not in scope"
CFG="${HERMES_CONFIG:-${HOME:-/root}/.hermes/config.yaml}"
if [ ! -f "$CFG" ]; then
    note "no config at $CFG — skipping (set HERMES_CONFIG to point at it)"
elif ! command -v python3 >/dev/null 2>&1; then
    bad "python3 not available — cannot parse $CFG, so this check did not run"
else
    # A real YAML parse. The previous awk version only recognised one exact
    # layout: 4-space indent, tabs, an inline list, quoted entries, a trailing
    # comment or any nesting all reported OK while terminal/file were granted.
    set +e
    CLI_TOOLS="$(HERMES_CFG="$CFG" python3 - <<'PY'
import os, sys
try:
    import yaml
except ImportError:
    print("__NOYAML__"); sys.exit(0)
try:
    with open(os.environ["HERMES_CFG"], encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh) or {}
except Exception as exc:                      # noqa: BLE001
    print("__ERROR__" + str(exc)); sys.exit(0)

found = []
def walk(node):
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "platform_toolsets" and isinstance(value, dict):
                for entry in (value.get("cli") or []):
                    found.append(str(entry).strip())
            walk(value)
    elif isinstance(node, list):
        for item in node:
            walk(item)
walk(cfg)
print("\n".join(found))
PY
)"
    PARSE_STATUS=$?
    set -e
    case "$CLI_TOOLS" in
        __NOYAML__*)
            bad "python3 has no yaml module — cannot parse $CFG, so this check did not run" ;;
        __ERROR__*)
            bad "could not parse $CFG: ${CLI_TOOLS#__ERROR__}" ;;
        *)
            if [ "$PARSE_STATUS" -ne 0 ]; then
                bad "config parse failed (status $PARSE_STATUS)"
            elif [ -z "$CLI_TOOLS" ]; then
                ok "platform_toolsets.cli grants nothing extra"
            else
                printf '%s\n' "$CLI_TOOLS" | sed 's/^/     granted: /'
                if printf '%s\n' "$CLI_TOOLS" | grep -Eqi '^(terminal|file|code_execution|browser|computer_use|shell)$'; then
                    bad "platform_toolsets.cli still grants shell/file tools. If 'hermes -t'"
                    bad "MERGES with these rather than replacing them, the lockdown is not"
                    bad "real. Clear the cli: list in $CFG, or confirm -t replaces it."
                else
                    ok "platform_toolsets.cli grants no shell/file tools"
                fi
            fi ;;
    esac
fi

# ── 5. a real one-shot with the new flags still reaches the KB ───────────
say "5. Smoke test — one read-only prompt with the new flags"
if [ "$FAILED" -ne 0 ]; then
    bad "skipping the live run: a check above failed, so the lockdown is unproven"
    bad "and this step would launch a root agent under it. Fix the above first."
elif [ -n "${SKIP_LIVE:-}" ]; then
    note "SKIP_LIVE set — not running the live prompt"
else
    SMOKE_PROMPT="Call the search_kb tool from the buttonsbebe_kb MCP server with query \"return policy\" and k 2. \
Begin your reply with the exact token KBOK: followed by a one-line summary of what you found. \
Do not write, post, tag or send anything anywhere. Do not run any shell command."
    # `timeout` is GNU coreutils; present on the VPS, absent on stock macOS.
    if command -v timeout >/dev/null 2>&1; then
        note "running: hermes -t $TOOLSETS -z '<kb lookup>'  (90s timeout)"
        set +e
        SMOKE="$(timeout 90 hermes -t "$TOOLSETS" -z "$SMOKE_PROMPT" 2>&1)"
        SMOKE_STATUS=$?
        set -e
    else
        note "running: hermes -t $TOOLSETS -z '<kb lookup>'  (no timeout available)"
        set +e
        SMOKE="$(hermes -t "$TOOLSETS" -z "$SMOKE_PROMPT" 2>&1)"
        SMOKE_STATUS=$?
        set -e
    fi
    printf '%s\n' "$SMOKE" | head -20 | sed 's/^/     /'
    if [ "$SMOKE_STATUS" -ne 0 ]; then
        bad "hermes exited $SMOKE_STATUS. Do NOT deploy."
    elif [ -z "$(printf '%s' "$SMOKE" | tr -d '[:space:]')" ]; then
        bad "empty output — Hermes produced nothing. Do NOT deploy."
    elif printf '%s' "$SMOKE" | grep -qiE "unknown toolset|no such toolset|invalid toolset|unrecognized"; then
        bad "Hermes rejected a toolset name — fix HERMES_TOOLSETS before deploying."
    elif printf '%s' "$SMOKE" | grep -qiE "approve|approval required|\[y/n\]|permission denied for tool"; then
        bad "looks like it stopped on an approval prompt. Investigate before deploying;"
        bad "HERMES_SKIP_APPROVAL=1 is the temporary unblock."
    elif ! printf '%s' "$SMOKE" | grep -q "KBOK:"; then
        # Require a POSITIVE signal. Checking only for the absence of a few
        # error strings meant any other failure - "connection refused", a
        # stack trace - read as a pass and printed "safe to restart".
        bad "no KBOK: token in the reply, so the KB tool did not answer."
        bad "Do NOT deploy — the allow-list is probably wrong."
    else
        ok "one-shot reached the knowledge base with the locked-down toolset"
        note "read the summary above: it should mention real return-policy content."
    fi
fi

say "Result"
if [ "$FAILED" -eq 0 ]; then
    printf '  \033[32mAll checks passed.\033[0m Safe to restart buttonsbebe-processor.\n\n'
    exit 0
fi
printf '  \033[31mSomething failed above. Do NOT restart the processor yet.\033[0m\n\n'
exit 1
