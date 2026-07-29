#!/usr/bin/env bash
# =============================================================================
#  heartbeat.sh — Buttons Bebe processor liveness check (dead-man's switch).
#
#  Runs from a systemd timer every few minutes. If the processor looks DOWN, or
#  has gone quiet for PROCESSOR_STALE_MINUTES, it POSTs one short alert to the
#  owner's WhatsApp via the whatsapp-connect service, and one "back up" message
#  when it recovers. It never repeats the down alert while the outage lasts.
#
#  AUTH: this uses the SAME contract as processor/whatsapp_notifier.py —
#    POST $WHATSAPP_SEND_URL
#    Authorization: Bearer $WA_SEND_SECRET
#    {"text": "..."}
#  Do NOT reintroduce the older token-in-the-URL pattern; the secret must stay
#  in the header so it never lands in an access log.
#
#  SAFETY: this script must NEVER take anything else down. If a required tool
#  or env var is missing it logs the reason and exits 0. It only ever READS
#  systemd/journal state and (best effort) POSTs one message.
#
#  INSTALL (VPS):
#    1. install -m 755 processor/heartbeat.sh "/root/Buttonsbebe Agent/processor/heartbeat.sh"
#    2. cp deploy/systemd/buttonsbebe-heartbeat.{service,timer} /etc/systemd/system/
#    3. systemctl daemon-reload
#       systemctl enable --now buttonsbebe-heartbeat.timer
#    4. verify: systemctl list-timers | grep buttonsbebe-heartbeat
#               journalctl -u buttonsbebe-heartbeat -n 20
# =============================================================================
set -u

log() { echo "[heartbeat $(date -u +%FT%TZ)] $*" >&2; }

# --- configuration (all overridable via the environment / EnvironmentFile) ---
UNIT="${PROCESSOR_UNIT:-buttonsbebe-processor}"
STALE_MIN="${PROCESSOR_STALE_MINUTES:-10}"
STATE_FILE="${HEARTBEAT_STATE_FILE:-/var/lib/buttonsbebe/heartbeat.state}"
SEND_URL="${WHATSAPP_SEND_URL:-}"
SEND_SECRET="${WA_SEND_SECRET:-}"

# The state file must survive between timer firings, so it cannot live in a
# PrivateTmp namespace. Fall back to /tmp only if /var/lib is not writable.
STATE_DIR="$(dirname "$STATE_FILE")"
if ! mkdir -p "$STATE_DIR" 2>/dev/null; then
    STATE_FILE="/tmp/buttonsbebe-heartbeat.state"
    log "cannot create $STATE_DIR — falling back to $STATE_FILE"
fi

# --- JSON string escaping (no python/jq dependency) --------------------------
json_escape() {
    printf '%s' "$1" | sed -e 's/\\/\\\\/g' -e 's/"/\\"/g' | tr '\n\r\t' '   '
}

# --- best-effort alert delivery (never fails the caller) ---------------------
send_alert() {
    msg="$1"
    missing=""
    [ -z "$SEND_URL" ] && missing="WHATSAPP_SEND_URL"
    [ -z "$SEND_SECRET" ] && missing="${missing:+$missing, }WA_SEND_SECRET"
    if [ -n "$missing" ]; then
        log "$missing not set — cannot deliver; logging only: $msg"
        return 0
    fi
    if ! command -v curl >/dev/null 2>&1; then
        log "curl not installed — cannot deliver; logging only: $msg"
        return 0
    fi
    if curl -fsS -m 15 -X POST "$SEND_URL" \
            -H "Content-Type: application/json" \
            -H "Authorization: Bearer $SEND_SECRET" \
            -d "{\"text\": \"$(json_escape "$msg")\"}" >/dev/null 2>&1; then
        log "alert delivered to WhatsApp"
    else
        log "alert POST failed (continuing anyway)"
    fi
    return 0
}

# --- 1. we need systemd to inspect the service -------------------------------
if ! command -v systemctl >/dev/null 2>&1; then
    log "systemctl not available (not a systemd host?) — nothing to check; exiting 0"
    exit 0
fi

# --- 2. decide whether the processor is alive --------------------------------
alive=1
reason=""

active="$(systemctl is-active "$UNIT" 2>/dev/null || true)"
if [ "$active" != "active" ]; then
    alive=0
    reason="service '$UNIT' is '${active:-unknown}' (expected 'active')"
elif command -v journalctl >/dev/null 2>&1; then
    # Active — but is it doing anything? The orchestrator emits an idle
    # heartbeat line every PROCESSOR_HEARTBEAT_SECONDS (default 120s) even
    # with an empty queue, so total silence for the whole window means the
    # loop is wedged, not merely quiet.
    lines="$(journalctl -u "$UNIT" --since "${STALE_MIN} min ago" --no-pager -q 2>/dev/null | wc -l | tr -d ' ')"
    if [ "${lines:-0}" -eq 0 ]; then
        alive=0
        reason="no journal output from '$UNIT' in the last ${STALE_MIN} min (possibly hung)"
    fi
else
    log "journalctl not available — relying on the service-active check only"
fi

# --- 3. act on the verdict, de-duping repeat alerts --------------------------
if [ "$alive" -eq 0 ]; then
    if [ -f "$STATE_FILE" ]; then
        log "processor still down ($reason) — alert already sent, staying quiet"
    else
        log "PROCESSOR DOWN: $reason"
        send_alert "Buttons Bebe alert: the support processor looks DOWN. ${reason}. New tickets may not be getting draft replies. Please check the server."
        : > "$STATE_FILE" 2>/dev/null || true
    fi
else
    if [ -f "$STATE_FILE" ]; then
        log "processor recovered — clearing alert state"
        send_alert "Buttons Bebe: the support processor is back up and processing tickets again."
        rm -f "$STATE_FILE" 2>/dev/null || true
    else
        log "processor healthy ('$UNIT' active with recent activity)"
    fi
fi

exit 0
