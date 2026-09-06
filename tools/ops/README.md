# Production operations: reviewed manual apply

These scripts never enable inbox Send, connect intake, or change Shopify/Gorgias
credentials. Root reviews and applies them on srv1766050. Keep the existing
console and Gorgias webhook active; do not run the retired full-root rollback.

## Isolated inbox runtime

`helpdesk-inbox.service` runs as the dedicated `bb-inbox` account. Code and the
hash-locked venv live under `/opt/buttonsbebe/inbox`, owned by root and readable
but not writable by the account. SQLite state alone lives under
`/var/lib/buttonsbebe-inbox`, owned by the account. `ProtectHome=true` denies the
old shared `/root` credentials; strict filesystem and localhost network rules
limit the service. Initial limits are 512 MiB and 64 tasks. Observe memory and
startup failures before changing limits; do not remove restrictions blindly.

1. Verify old intake/seen files are absent or run the reviewed explicit migration
   CLI against a stopped old inbox. Do not infer an empty store from a read error.
   Preserve originals and take a SQLite backup of any existing new store.
2. Prepare a **new** candidate directory from the reviewed integrated source:
   `python3 tools/ops/inbox_runtime.py prepare --source REVIEWED_ROOT --stage /opt/buttonsbebe/inbox-stage-RELEASE`.
   Preparation installs only hash-locked dependencies. It does not start a service.
3. Record the current `/etc/systemd/system/helpdesk-inbox.service` SHA256 and
   review the new unit. The source must contain the ASGI server and lock file.
4. After validating state, invoke `inbox_runtime.py apply` with `--stage`,
   `--unit REVIEWED_ROOT/deploy/systemd/helpdesk-inbox.service`,
   `--expected-unit-sha256 REVIEWED_SHA`, and `--state-verified`.
   The script validates Linux unit syntax, installs the identity, stops only the
   inbox, switches code/unit, probes Send and bridge locks, and restores the old
   code/unit on failure. It prints a protected backup directory for rollback.
5. Independently verify account, listening address, authenticated browser/API
   routing, assets, and read-only state. The script's two safety probes are not
   a complete acceptance test. Enable `helpdesk-inbox.service` only after success.
6. To undo this manual installation, run `inbox_runtime.py rollback --backup
   THE_RECORDED_DIRECTORY` while no later code deployment is in progress.
   It restores code and unit only; it never restores or deletes customer data.
   Repeated completed rollback is a no-op. Retain the restricted account/state.

The deployment receiver manages later inbox source updates at this isolated
path. The venv is a separate prepared dependency artifact; do not move a venv
out of `/root` or run the new account against credentials in the main app tree.
The CLI takes the receiver deployment lock before apply or rollback and refuses
a concurrent release. A later code release requires
fresh review before using an older manual rollback directory.

## Caddy and conservative core restrictions

Materialize **only reviewed differences** into the existing live support
fragment; never overwrite secrets with redacted source placeholders.

- Inbox uses `handle /inbox/*` plus explicit `route`: authentication executes
  before stripping `/inbox`, then all service routes reach port 8766. This keeps
  original URI/method/Origin available to auth and preserves `/console/api`.
- Historical `/qa` and `/qa/*` return404. Files remain on disk for recovery.
- Existing URI/Referer log redaction remains intact.
- Webhook/processor units add NoNewPrivileges, PrivateTmp and kernel protection,
  while preserving current root runtime paths and existing secret drop-ins.
  They remain privileged legacy components; this is not complete isolation.
- Heartbeat keeps its persistent state outside PrivateTmp. EnvironmentFile is
  intentionally unquoted: systemd's EnvironmentFile parser accepts spaces as
  part of this path and rejects surrounding quotes. Documentation `%` is escaped.

Validate the complete staged Caddy configuration on the actual Linux Caddy
version, then reload it. Apply core units during the coordinated release, not
mid-job. Preserve installed credential-bearing drop-ins. Run Linux
`systemd-analyze verify` and the included Caddy integration test before applying.

After **all** reviewed config changes are applied and verified, root updates the
`deploy/systemd` and `deploy/caddy` directory fingerprints in
`/etc/buttonsbebe-deploy-approved-config.sha256` using the receiver's exact
sorted SHA256 algorithm. Record hashes of actual applied unit/fragment files
separately. Never approve source config before its corresponding live changes
are applied. The CD receiver does not install these units or Caddy fragments.

## Encrypted backups and failure visibility

The backup service reads the existing public recipient certificate
`/etc/buttonsbebe-backup-recipient.pem`; **no private decryption key belongs on
this VPS**. It uses the SQLite backup API, validates each snapshot, encrypts the
archive with OpenSSL CMS AES-256, and removes temporary plaintext on normal
completion. The six-hour timer writes only its own encrypted files in
`/opt/buttonsbebe/backups/scheduled`; 14-day retention preserves at least three
verified snapshots and never prunes manually created backups.

Before enabling the timer, manually run the service once and decrypt/restore a
copy off-host using the owner's existing protected key. Check integrity and
manifest SHA256 values. Root already has the intended public cert installed;
do not generate a replacement recipient or invent an off-host upload endpoint.
The timer creates local encrypted copies only. Off-host copies must use the
separately reviewed destination/transport and must be observed for freshness.

`/var/lib/buttonsbebe/backup-status.json` records status, last attempt, last
success and only an error class. Unit failure is nonzero and appears in the
journal. Alert on failed status or last success older than eight hours; a
healthy processor does not establish healthy backups. An off-host monitor is
still required to detect complete VPS/network failure. A machine crash can
leave a private `.incomplete-*` directory; inspect/recover it under root rather
than treating it as a completed encrypted backup.

To stop scheduling, disable the backup timer; leave all existing backups and
keys intact. A backup is never automatically restored by deployment or by this
job. `sqlite_backup.py` is also available for one-off private snapshots.

## Listener containment inventory

`listener_inventory.py` reports selected ports, loopback binding, PID, known
service name, and whether an unmanaged Python preview has a deleted working
directory. It never prints command lines, environment variables or token paths.

Observed before remediation: Hermes9119 is owned by
`buttonsbebe-hermes-dashboard.service`; exchange4100 by `exchange-proxy.service`;
Python8099 is an unmanaged deleted-directory preview; redo3210 is separate and
unmanaged by systemd. Bind Hermes/exchange only after reviewing their exact
launch code and preserving Caddy reachability. Revalidate PID/start identity
before stopping the stray preview. Do not blindly stop redo3210: determine its
login/API protection and legitimate consumers first. No listener is stopped or
firewall changed by the inventory tool.
