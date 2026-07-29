#!/usr/bin/env bash
# =============================================================================
#  verify_hermes_toolset.sh — run this on the VPS BEFORE restarting the
#  processor with the new tool allow-list (DEV-ISSUES #8).
#
#  WHY: a misspelled toolset name is silent. Hermes does not error; it just
#  loses the tool, and drafts quietly get worse with nothing in the logs.
#  This script proves the names are right before anything goes live.
#
#  READ-ONLY. It lists configuration and runs one throwaway one-shot prompt
#  about store policy. It never writes to Gorgias, Shopify, Redo or the queue,
#  and it never touches a real ticket.
#
#  USAGE:
#     bash tools/verify_hermes_toolset.sh
#     HERMES_TOOLSETS="mcp-a,mcp-b" bash tools/verify_hermes_toolset.sh
# =============================================================================
set -u

TOOLSETS="${HERMES_TOOLSETS:-mcp-buttonsbebe_kb,mcp-buttonsbebe_redo,mcp-buttonsbebe_gorgias}"
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
MCP_OUT="$(hermes mcp list 2>&1 || true)"
printf '%s\n' "$MCP_OUT" | sed 's/^/     /'
for server in $EXPECTED_SERVERS; do
    if printf '%s' "$MCP_OUT" | grep -q -- "$server"; then
        ok "$server registered"
    else
        bad "$server NOT found in 'hermes mcp list'"
    fi
done

# ── 3. every toolset we ask for maps to a registered server ──────────────
say "3. Toolset names match the server keys"
IFS=',' read -r -a WANTED <<< "$TOOLSETS"
for ts in "${WANTED[@]}"; do
    ts="$(printf '%s' "$ts" | tr -d '[:space:]')"
    [ -z "$ts" ] && continue
    server="${ts#mcp-}"
    if [ "$server" = "$ts" ]; then
        note "$ts is not an mcp- toolset — skipping the server-key check"
        continue
    fi
    if printf '%s' "$MCP_OUT" | grep -q -- "$server"; then
        ok "$ts -> server '$server'"
    else
        bad "$ts -> no server called '$server'. THIS WOULD SILENTLY LOSE THE TOOL."
    fi
done

# ── 4. terminal / file must not be granted to the CLI platform ───────────
say "4. Dangerous toolsets are not in scope"
CFG="${HERMES_CONFIG:-$HOME/.hermes/config.yaml}"
if [ -f "$CFG" ]; then
    CLI_BLOCK="$(awk '/^platform_toolsets:/{f=1;next} f&&/^[a-z_]+:/{exit} f&&/^  cli:/{c=1;next} c&&/^  [a-z_]+:/{exit} c' "$CFG" 2>/dev/null)"
    if [ -z "$CLI_BLOCK" ]; then
        ok "platform_toolsets.cli grants nothing extra"
    else
        printf '%s\n' "$CLI_BLOCK" | sed 's/^/     /'
        if printf '%s' "$CLI_BLOCK" | grep -qE '^\s*-\s*(terminal|file|code_execution|browser|computer_use)\s*$'; then
            bad "platform_toolsets.cli still grants terminal/file. If 'hermes -t'"
            bad "MERGES with these rather than replacing them, the lockdown is not"
            bad "real. Clear the cli: list in $CFG, or confirm -t replaces it."
        else
            ok "platform_toolsets.cli grants no shell/file tools"
        fi
    fi
else
    note "no config at $CFG — skipping (set HERMES_CONFIG to point at it)"
fi

# ── 5. a real one-shot with the new flags still reaches the KB ───────────
say "5. Smoke test — one read-only prompt with the new flags"
note "running: hermes -t $TOOLSETS -z '<kb lookup>'  (60s timeout)"
SMOKE="$(timeout 90 hermes -t "$TOOLSETS" -z \
    "Call the search_kb tool from the buttonsbebe_kb MCP server with query \"return policy\" and k 2. \
Print a one-line summary of what you found. Do not write, post, tag or send anything anywhere. \
Do not run any shell command." 2>&1 || true)"
printf '%s\n' "$SMOKE" | head -20 | sed 's/^/     /'
if [ -z "$(printf '%s' "$SMOKE" | tr -d '[:space:]')" ]; then
    bad "empty output — Hermes produced nothing. Do NOT deploy."
elif printf '%s' "$SMOKE" | grep -qiE "approve|approval required|\[y/n\]|permission denied for tool"; then
    bad "looks like it stopped on an approval prompt. Investigate before deploying;"
    bad "HERMES_SKIP_APPROVAL=1 is the temporary unblock."
elif printf '%s' "$SMOKE" | grep -qiE "unknown toolset|no such toolset|invalid toolset"; then
    bad "Hermes rejected a toolset name — fix HERMES_TOOLSETS before deploying."
else
    ok "one-shot returned output with the locked-down toolset"
    note "read the summary above: it should mention real return-policy content."
    note "If it is vague or says it has no tools, the allow-list is wrong."
fi

say "Result"
if [ "$FAILED" -eq 0 ]; then
    printf '  \033[32mAll checks passed.\033[0m Safe to restart buttonsbebe-processor.\n\n'
    exit 0
fi
printf '  \033[31mSomething failed above. Do NOT restart the processor yet.\033[0m\n\n'
exit 1
