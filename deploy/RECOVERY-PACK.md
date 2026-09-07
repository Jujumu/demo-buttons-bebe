# Explicit encrypted recovery pack

This operator tool supplements the SQLite-only scheduled backup. It does not stop services, change live files, upload backups, or install a new timer. It cannot establish whole-service disaster recovery on its own.

## Review the private plan first

Copy `recovery-plan.example.json` into a root-owned mode0600 file outside the checkout. Its zero commit/fingerprint placeholders are not usable values. The template is a starting inventory, not a verified closure of this host's configuration. Resolve the exact released commit and independently compare the installed recipient certificate's SHA256 DER fingerprint with the trusted Mac certificate; the pack also checks at least one day of remaining validity.

Review every entry before capture. Add each actual Buttons Bebe Caddy import target, active supported unit, relevant drop-in, custom support skill, and explicitly referenced EnvironmentFile. The built-in scope intentionally rejects general root paths, Hermes history/cache/sandboxes, venvs, node_modules, and the LanceDB index. Extra EnvironmentFiles or custom skill locations outside the reviewed scope require a source policy review, not a catch-all path override. There is no automatic arbitrary-root glob.

Caddy symlinks require an explicit recipe, for example an entry with `kind: symlink`, its absolute `path`, and its approved absolute `target`, plus a separate `kind: file` entry for that target. The actual link must resolve lexically to that target. Parent symlinks and links inside directory trees are rejected. Restore validation preserves the link recipe in the encrypted manifest but creates no symlinks. Never capture all shared-host Caddy sites.

Prepare `/opt/buttonsbebe/backups/recovery-input` privately with the exact released source archive and a reviewed operational JSON receipt: release/lock hashes, installed interpreter/Node/Caddy/Hermes versions, Hermes compatibility patch hash, service identities and enabled timers. This is an explicit caller-prepared input; this tool does not invent those facts or certify an archive matches the deployed source. Include the source deployment manifest and applied-config fingerprints in the plan. Rebuild dependencies from the locks and the KB index from durable corpora later, in isolation.

Each requested path is required: missing or unreadable files fail capture. Remove a genuinely absent optional path only after documenting that absence privately; do not hide a missing required recovery component. The learned tree includes its ledger and notices include their JSON. An empty WhatsApp auth directory is recorded as empty; this does not prove a linked session can be restored.

## Capture after explicit operator approval

Create the destination as a root-owned real mode0700 directory under the protected backup root. With reviewed private plan and recipient in place:

```bash
python3 tools/ops/recovery_pack.py --plan /root/buttonsbebe-recovery-plan.json
```

Regular files are copied through no-follow descriptors, with before/after hashes and inode/metadata checks, at most three attempts. Tree membership and owner/mode metadata are compared again after capture. SQLite uses the backup API and integrity checks, with a two-minute deadline per database. Limits: 20,000 members, 64MiB per regular file, 512MiB per database, 1GiB combined payload, 8MiB manifest. Exceeding a limit fails; no silent truncation.

These are **independent SQLite snapshots and individually stable files, not a global point-in-time snapshot**. A file can change after its successful capture. KB has no global writer lock and multi-file WhatsApp auth can be mutually inconsistent despite each file being stable; obtain separate approval to quiesce relevant writers when that consistency is required. The tool never stops them itself.

CMS AES-256-GCM encrypts payloads and the sensitive path/mode/owner/hash manifest. Plaintext exists only under a private temporary directory and is removed on completion/failure. Ciphertext is fsynced and published without overwrite, followed by a public receipt containing only time, class, count, ciphertext size/hash, and verification state. Plaintext removal is unlinking, not secure erasure. Transfer only ciphertext, its independently trusted hash, and the private plan through the approved off-host process; no destination is inferred.

## Isolated validation on the trusted Mac

Use a fresh mode0700 destination, the matching private plan (mode0600), the recipient certificate, and owner-private key. Keep the private key solely on the trusted Mac. Use the ciphertext hash obtained from the trusted transfer receipt:

```bash
python3 tools/ops/recovery_restore.py --ciphertext /private/path/recovery.cms \
  --ciphertext-sha256 TRUSTED_SHA256 --certificate /private/path/recipient.pem \
  --private-key /private/path/recipient-key.pem --plan /private/path/recovery-plan.json \
  --destination /private/path/fresh-validation
```

Validation checks the trusted ciphertext hash and certificate fingerprint, decrypts into private temporary space, rejects unsupported tar extensions/traversal/links/duplicates/oversized members, requires the exact approved plan and payload set, checks every hash and SQLite integrity, and publishes only validated neutral payload filenames mode0600 plus the private manifest. It never extracts original absolute paths, applies recorded ownership, creates symlinks, calls providers, or starts services. Invalid plaintext intermediates are removed by the CLI. Success proves file/SQLite restoration, not provider credential validity, deployability, source provenance, global consistency, or delivery reconciliation.

Before any later service restoration, inspect accepted-event gaps and pending/uncertain send operations, validate source/dependency receipts, rebuild KB search in isolation, verify routing/authentication and provider access, and decide separately when to start processing. Never replay an ambiguous send automatically. Off-host availability, full restore time, and a complete controlled restore drill remain separate proofs.


## Reviewed root-user Hermes gateway unit

The exact `/root/.config/systemd/user/hermes-gateway.service` file is included in the example plan and is the only allowed root-user unit. Its verified fragment and working directory point to `/root/.hermes`, whose SOUL identifies Buttons Bebe. This does not prove every configured gateway channel belongs to Buttons Bebe. No gateway history, session database, pending jobs, or general root-user unit directory has been added to the scope.

On a host where this optional gateway component is genuinely absent, document that absence in the private recovery receipt and remove that exact example entry before packing. The tool never silently skips a missing file. Additional user-unit drop-ins or aliases require a separate exact-scope review.

A later operator may reconstruct the recorded user-unit file and permissions while all processing remains stopped. First reconcile ambiguous sends, accepted-event gaps, and pending gateway work; inspect the restored gateway's channel identities and credential validity and approve the intended channels separately. Only after that review, use the root user's existing systemd user manager (not the system manager) to reload and explicitly enable/start the single unit:

```bash
systemctl --user daemon-reload
systemctl --user enable hermes-gateway.service
systemctl --user start hermes-gateway.service
```

These are manual root-user recovery steps, not commands run by the pack or validator. Do not enable lingering, start a missing user manager, replay queued work, or activate other channels as an inferred part of restoration. Confirm the existing user-manager context before those commands and verify the intended gateway afterward.
