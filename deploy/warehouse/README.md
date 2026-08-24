# Warehouse Shopify-write hardening

The warehouse application lives outside this repository at `/opt/warehouse`.
These small tools keep the two recovery hardenings reproducible
without copying the warehouse application into the support-agent repository:

1. `src/server.js` binds Express to `127.0.0.1` so port 4000 is not exposed
   directly to the internet.
2. `src/shopify.js` rejects every GraphQL mutation at the final network
   boundary unless `SHOPIFY_MUTATIONS_ENABLED` is explicitly enabled. The
   known price, product-status, and variant-barcode functions additionally
   require `SHOPIFY_CONTENT_WRITES_ENABLED`. Both absent variables are
   disabled, so new mutation callers also fail closed.

The patcher only accepts the exact known pre-patch anchors. It aborts on source
drift, a partial guard, a symlink target, a concurrent edit, or a failed
post-write check. It never calls Shopify, sends a webhook, runs the warehouse
service, or restarts systemd.

## Read-only check

On a host containing the warehouse checkout:

```bash
sudo deploy/warehouse/check-safety-patch.sh /opt/warehouse
```

This reads source only and should report `PASS` before the service is started.

## Apply, only after explicit production approval

The current task intentionally does not run this command. When an approved
operator needs to apply the source recovery:

```bash
sudo deploy/warehouse/apply-safety-patch.sh /opt/warehouse
```

The command creates a dated root-only backup under:

```text
/opt/warehouse/.codex-safety-backups/<UTC timestamp>/
```

The backup is a byte-for-byte source recovery copy. It is not a sanitizer: if
source ever contained an embedded secret, the backup would retain it. The
directory is therefore mode `0700`; keep credentials out of source and treat
these backups as production-sensitive.

It does not restart `warehouse.service`. Review the output and run the
read-only check again before a separately approved service restart. Keep the
backup directory until live health and the write guard have been verified.

For a rehearsal against a disposable copy:

```bash
deploy/warehouse/apply-safety-patch.sh /path/to/warehouse-copy --dry-run
```

## Rollback warning

Rollback is emergency-only. A pre-write-lock backup can remove the fail-closed
guard and must never be followed by a service restart without a new safety
review. The command requires an explicit acknowledgement and creates another
backup before restoring:

```bash
sudo deploy/warehouse/rollback-safety-patch.sh \
  /opt/warehouse \
  /opt/warehouse/.codex-safety-backups/<UTC timestamp> \
  --acknowledge-write-enable-risk
```

Always run `check-safety-patch.sh` after rollback. A failed check is a stop
condition, not a prompt to guess at a source edit.

## Verification

The repository regression test checks the exact patch anchors, applies the
patch to a temporary fixture, proves the operation is idempotent, proves drift
aborts without changing files, and verifies that the KB systemd target points
to an executable `sync-products.sh`.

Run it locally:

```bash
python3 -m unittest deploy.tests.test_warehouse_safety_assets -v
```

The KB product sync remains a read-only Shopify export that writes only local
knowledge-base files. This hardening does not run that sync.

After a reviewed warehouse source deployment, create the runtime inventory
manifest consumed by `tools/shopify_safety.py`:

```bash
cd /opt/warehouse
find src -type f -name '*.js' -print0 | LC_ALL=C sort -z | xargs -0 -r sha256sum \
  > .codex-safety-source.sha256
chown root:root .codex-safety-source.sha256
chmod 0600 .codex-safety-source.sha256
```

Restart `warehouse.service` after installing hardened source, then run the
monitor. It deliberately reports drift when the process predates `shopify.js`
or when any JavaScript file is added, removed, or changed without regenerating
the reviewed manifest.
