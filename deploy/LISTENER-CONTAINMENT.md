# Reviewed listener containment

`tools/ops/contain_listeners.py` is a root-only manual operation. It never runs
through CD. Review and apply one service at a time. It preserves the current
unit/source except the exact public-to-localhost bind expression, and never
changes environment values, PM2 apps, firewall rules, or Caddy configuration.

The root reviewer must supply current PID, `/proc/PID/stat` start ticks and SHA256
of both the service fragment and edited source. For Hermes these are the same
file. Changed identities, hashes, drop-ins, or bind expressions fail closed.
Do not paste the complete unit, process command, environment, or auth header
into logs or chat. `listener_inventory.py` provides sanitized listener metadata.

```sh
python3 tools/ops/contain_listeners.py hermes \
  --expected-pid REVIEWED_PID --expected-start-ticks REVIEWED_TICKS \
  --expected-unit-sha256 REVIEWED_UNIT_SHA \
  --expected-source-sha256 REVIEWED_UNIT_SHA

python3 tools/ops/contain_listeners.py exchange \
  --expected-pid REVIEWED_PID --expected-start-ticks REVIEWED_TICKS \
  --expected-unit-sha256 REVIEWED_UNIT_SHA \
  --expected-source-sha256 REVIEWED_SERVER_JS_SHA
```

The two exact units are `buttonsbebe-hermes-dashboard.service` and
`exchange-proxy.service`. Caddy continues proxying `127.0.0.1:9119` and
`127.0.0.1:4100`. The script compares HEAD status/content-type on the existing
HTTPS origin and localhost before/after; it never reads response bodies.
For authenticated Hermes continuity, optionally pass
`--proxy-authorization-file /PRIVATE/ROOT/0600/FILE` containing the existing
complete Authorization header value. A public 401 continuity check proves the
Caddy auth boundary remains up, not that an authenticated page was rendered;
the separate localhost check confirms backend availability.

Private dated source backups and metadata are fsynced before replacement.
`systemd-analyze verify` or `node --check` validates the candidate. Only the named
service restarts. The final listener must be loopback-only and owned by its
current service PID. Failure retains the contained source and reports failure;
it does not automatically reopen a public endpoint. The operator should repair
service startup or proxy issues while keeping the local bind. Restoring an old
backup would reopen exposure and requires a separately reviewed alternative
containment plan. Re-running with stale pre-change hashes safely refuses.

The deleted-directory preview can be stopped only when its exact command is
Python `-m http.server 8099`, its cwd is still deleted, and PID/start ticks plus
socket ownership match the review:

```sh
python3 tools/ops/contain_listeners.py preview \
  --expected-pid REVIEWED_PID --expected-start-ticks REVIEWED_TICKS
```

Linux pidfd signaling avoids PID-reuse races. Only SIGTERM is sent, with no
replacement or restart. If it persists, inspect it; the script does not escalate
or signal any new owner of the port. No preview files are removed.
