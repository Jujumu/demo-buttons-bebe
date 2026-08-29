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
#    1. install -m 755 processor/heartbeat.sh "/opt/buttonsbebe/processor/heartbeat.sh"
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
# Deliberately its OWN variable. PROCESSOR_STALE_MINUTES means "requeue a job
# stuck in `processing` after N minutes" to the orchestrator; overloading it
# here meant that tuning the queue silently widened or narrowed the
# dead-man's switch.
STALE_MIN="${HEARTBEAT_STALE_MINUTES:-10}"
STATE_FILE="${HEARTBEAT_STATE_FILE:-/var/lib/buttonsbebe/heartbeat.state}"
SEND_URL="${WHATSAPP_SEND_URL:-}"
SEND_SECRET="${WA_SEND_SECRET:-}"

# The state file must survive between timer firings, so it cannot live in a
# PrivateTmp namespace. Fall back to /tmp only if /var/lib is not WRITABLE —
# `mkdir -p` on a directory that already exists returns 0 even on a read-only
# filesystem, so testing mkdir alone let a full or remounted-ro disk send an
# alert every five minutes forever.
_state_is_writable() {
    _dir="$(dirname "$1")"
    mkdir -p "$_dir" 2>/dev/null || return 1
    # Probe with a THROWAWAY file. Writing to the state file itself would
    # create the latch as a side effect, and every run would then believe an
    # alert had already been sent.
    _probe="$_dir/.heartbeat-write-probe.$$"
    if : > "$_probe" 2>/dev/null; then
        rm -f "$_probe" 2>/dev/null || true
        return 0
    fi
    return 1
}

if ! _state_is_writable "$STATE_FILE"; then
    log "state file $STATE_FILE is not writable — falling back to /tmp"
    STATE_FILE="/tmp/buttonsbebe-heartbeat.state"
    if ! _state_is_writable "$STATE_FILE"; then
        log "WARNING: no writable state file. De-duplication is off; this run"
        log "         may repeat an alert that was already sent."
    fi
fi

# Never truncate an arbitrary path as root. HEARTBEAT_STATE_FILE comes from
# the environment, and a typo ("/etc/passwd") would otherwise blank whatever
# it names. The name itself has to look like a heartbeat state file.
case "$(basename "$STATE_FILE")" in
    *heartbeat*.state) ;;
    *)
        log "refusing a state file that is not named *heartbeat*.state: $STATE_FILE"
        STATE_FILE="/tmp/buttonsbebe-heartbeat.state"
        ;;
esac

# --- JSON string escaping (no python/jq dependency) --------------------------
json_escape() {
    printf '%s' "$1" | sed -e 's/\\/\\\\/g' -e 's/"/\\"/g' | tr '\n\r\t' '   '
}

# --- best-effort alert delivery (never fails the caller) ---------------------
# Returns 0 ONLY if the message actually reached WhatsApp. The caller latches
# on that return value: if whatsapp-connect is down at the moment the
# processor dies — a reboot, an OOM, a full disk kills both — the alert must
# be retried on the next firing, not silently marked as sent. The original
# always returned 0, which disarmed the dead-man's switch permanently in
# exactly the correlated-failure case it exists for.
send_alert() {
    msg="$1"
    missing=""
    [ -z "$SEND_URL" ] && missing="WHATSAPP_SEND_URL"
    [ -z "$SEND_SECRET" ] && missing="${missing:+$missing, }WA_SEND_SECRET"
    if [ -n "$missing" ]; then
        log "$missing not set — cannot deliver; logging only: $msg"
        return 1
    fi
    if ! command -v curl >/dev/null 2>&1; then
        log "curl not installed — cannot deliver; logging only: $msg"
        return 1
    fi
    # --url, not a positional argument: a SEND_URL beginning with "-" would
    # otherwise be parsed by curl as an option.
    if curl -fsS -m 15 -X POST --url "$SEND_URL" \
            -H "Content-Type: application/json" \
            -H "Authorization: Bearer $SEND_SECRET" \
            -d "{\"text\": \"$(json_escape "$msg")\"}" >/dev/null 2>&1; then
        log "alert delivered to WhatsApp"
        return 0
    fi
    log "alert POST failed — will retry on the next firing"
    return 1
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
    # Active — but is it doing anything USEFUL? Counting journal lines was not
    # enough: _process_one_job catches every exception and logs an ERROR, then
    # the loop continues, so a processor failing 100% of tickets produces MORE
    # output than a healthy idle one and read as perfectly well.
    #
    # We look for the specific markers that only appear when the loop is
    # actually turning: the idle heartbeat the orchestrator emits every
    # PROCESSOR_HEARTBEAT_SECONDS, a completed job, or a fresh start.
    #
    # The -q is load-bearing: without it journalctl prints "-- No entries --"
    # on stdout and every empty window would look non-empty.
    healthy_markers="Processor idle heartbeat|Job completed|Job processor starting|Queue stats at startup"
    window="$(journalctl -u "$UNIT" --since "${STALE_MIN} min ago" --no-pager -q 2>/dev/null || true)"
    beats="$(printf '%s\n' "$window" | grep -Ec "$healthy_markers" || true)"
    if [ "${beats:-0}" -eq 0 ]; then
        alive=0
        total="$(printf '%s\n' "$window" | grep -c . || true)"
        if [ "${total:-0}" -eq 0 ]; then
            reason="no journal output from '$UNIT' in the last ${STALE_MIN} min (possibly hung)"
        else
            reason="'$UNIT' logged ${total} lines in the last ${STALE_MIN} min but completed no work (possibly failing every ticket)"
        fi
    fi
else
    log "journalctl not available — relying on the service-active check only"
fi

# --- 3. act on the verdict, de-duping repeat alerts --------------------------
if [ "$alive" -eq 0 ]; then
    if [ -f "$STATE_FILE" ]; then
        log "processor still down ($reason) — alert already delivered, staying quiet"
    else
        log "PROCESSOR DOWN: $reason"
        if send_alert "Buttons Bebe alert: the support processor looks DOWN. ${reason}. New tickets may not be getting draft replies. Please check the server."; then
            # Latch ONLY on a delivered message, so an undelivered alert is
            # retried in five minutes instead of being lost forever.
            : > "$STATE_FILE" 2>/dev/null || log "could not write $STATE_FILE — the next run may repeat this alert"
        else
            log "alert not delivered — staying unlatched so the next run retries"
        fi
    fi
else
    if [ -f "$STATE_FILE" ]; then
        log "processor recovered — clearing alert state"
        # Clear the latch whether or not the all-clear got through: the
        # outage is over, and a stuck latch would suppress the NEXT outage.
        send_alert "Buttons Bebe: the support processor is back up and processing tickets again." || true
        rm -f "$STATE_FILE" 2>/dev/null || true
    else
        log "processor healthy ('$UNIT' active and completing work)"
    fi
fi

exit 0
