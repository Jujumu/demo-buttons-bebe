# Manual scoped WhatsApp dependency switch

This helper is only for the reviewed candidate `/opt/buttonsbebe/whatsapp-candidate-18ca775`. It is not called by CD. Root's independent candidate npm install, 11 tests, zero-advisory audit, required module imports, and Curve fixture are prerequisites; the helper does not substitute for those proofs or install anything.

The approved operation replaces only `node_modules`, adopts the candidate `package.json`/`package-lock.json`, and removes the startup log's ` base=${BASE}` suffix from the existing live server. It does not copy the candidate server, change any routing/authentication value, touch the WhatsApp auth directory, or restart another service.

## Pre-review

Run the read-only inventory while holding the shared deployment lock, saving its JSON privately mode0600:

```bash
umask 077
python3 tools/ops/whatsapp_dependency_switch.py --inventory > /root/wa-switch-approved.json
```

Inspect/approve those live/candidate file hashes, complete node_modules tree digests, and the exact minimal patched-server hash against the independently tested candidate. Do not regenerate and automatically approve the plan during apply. The helper rejects changed hashes, missing fingerprints, a different qs version, or any Baileys version change. Its tree inventory rejects external symlinks/special files and caps 30,000 members/1GiB. Relative npm `.bin` links inside the module tree are supported.

Apply only after root reviews the concrete plan:

```bash
python3 tools/ops/whatsapp_dependency_switch.py --approved-plan /root/wa-switch-approved.json --apply
```

Apply acquires `/run/lock/buttonsbebe-deploy.lock`, requires the named unit active, live state `qr`, and auth directory empty, verifies atomic moves are on one filesystem, and saves old source/package files in a new private backup directory. It stops only `buttonsbebe-whatsapp-connect.service`, rechecks auth and hashes, atomically renames old modules into that backup and candidate modules into the live tree, and atomically replaces the three narrowly approved files. After restart, bounded local `/wa/status` checks must reach QR or connected state. The status client refuses redirects and ambient proxies and never prints QR/owner data. A legitimate pairing that arrives during startup is preserved.

On a detected failure, the helper stops that same unit, preserves the failed candidate modules under the private backup, restores old modules and original files/modes, starts the old service and verifies readiness. It never deletes or rewinds auth data—even if pairing data appeared during the operation. SIGINT/SIGTERM enter the same error path. If rollback itself fails, the journal marks `manual-recovery-required`; do not infer success from a restarted process alone.

The private `switch.json` journal records phases, reviewed hashes, and original modes. The successful receipt supplies its recovery directory ID under `/opt/buttonsbebe/backups/`. Source and module moves are atomic individually, not a whole-operation transaction. A host power loss or SIGKILL requires manual inspection of that journal and preserved files before restarting; do not rerun a stale plan or delete the original module backup. The helper does not rotate secrets or remove historical logs.

Synthetic tests cover successful exact changes, candidate readiness failure and rollback, preservation of independently arriving auth data, hash drift, linked/nonempty preflight rejection, deployment-lock contention, external symlinks, and minimal log redaction. No live switch was performed by those tests.
