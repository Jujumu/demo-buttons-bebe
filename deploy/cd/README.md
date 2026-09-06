# Production deployment

The receiver is privileged, manually installed infrastructure. A commit changing
this directory does **not** replace the installed receiver or helper. Review and
install both together; do not merge into auto-deploying main until the new
receiver is installed and the isolated Linux recovery harness passes.

## What a release owns

`source_release.py` is the versioned component manifest/policy. It inventories
SHA256 hashes, destination, modes and affected services for webhook, processor,
feedback, tools, KB code, KB admin, WhatsApp, inbox and helpdesk-agent. It also
ships both console HTML assets. A successful inventory is persisted under
`/var/lib/buttonsbebe-deploy/source-manifest.json`.

Inbox source is explicitly deployed under `/opt/buttonsbebe/inbox/console-src/`.
Its venv is `/opt/buttonsbebe/inbox/venv`; its database lives outside the code
root under `/var/lib/buttonsbebe-inbox/`. The historical `/root/Buttonsbebe Agent/
console-src/` copies are not deleted or used by this manifest.

Credentials, virtual environments, node_modules, databases, logs, WhatsApp
session state, KB index and **all KB corpora** (including editor-managed policies,
intents, FAQ, tickets and Shopify background) are never deployed or rolled back.
KB content changes require their existing reviewed content workflow and index
promotion; code deployment never rebuilds an index. These backups are source
recovery journals, not database backups or disaster recovery.

## Before installing this receiver

1. Run `python3 -m unittest deploy.tests.test_receiver_recovery -v` in an isolated
   Linux checkout. It uses temporary synthetic data and fake service/network
   commands. Tests must execute, not report skipped.
2. Install reviewed `source_release.py` as root-owned mode 0644 at
   `/usr/local/lib/buttonsbebe-deploy/source_release.py`; install the receiver
   script mode 0755 at `/usr/local/sbin/buttonsbebe-deploy-receive`.
3. Preserve the restricted SSH wrapper/sudo rule. CD does not accept arbitrary
   paths or commands. New GitHub archives contain `.buttonsbebe-release.json`
   with the verified workflow run number and exact commit. The receiver rejects
   missing/mismatched metadata and older successful workflow generations.
4. Apply Caddy/systemd changes manually, validate/reload them, and record both
   `deploy/systemd HASH` and `deploy/caddy HASH` source-directory fingerprints
   in `/etc/buttonsbebe-deploy-approved-config.sha256`. Also record applied
   absolute-path fingerprints as `/etc/path HASH` (path first, not sha256sum's
   default output). Every recorded applied file is checked before outage.
5. Keep runtime sources and manifests root-owned. Required services must already
   exist and be intentionally activated: the receiver preserves which services
   and maintenance timers were active, never starts previously stopped services.

## Dependency changes

CD never mutates or rewinds an environment. A changed/added/removed dependency
manifest fails before backups or service stops. An operator must prepare a
separate environment with the exact release manifests, run its tests, and
perform a reviewed environment switch with a compatible old environment kept
available. Only after that verified preparation, install the reviewed manifest
files into their target source locations so CD can verify matching hashes.
Do not simply copy manifests to bypass this prerequisite. For new inbox installs,
use its pinned requirements in its dedicated venv. Webhook/processor must use
`uv sync --locked`; CI now builds those same isolated locked environments.

Dependency upgrades needing coordinated old/new code or database compatibility
remain an explicit staged migration, not an automatic routine code release.
Database schema changes must remain backward-compatible with the journal's prior
code; a source rollback cannot undo a data migration and must never try to.

## Apply and recovery

The receiver holds a nonblocking host `flock` from intake through completion.
A competing invocation exits 75 before staging or stopping anything. Archives
are bounded, verified and immutable; same commit with different bytes is rejected.
A journal captures only changed source files. A first adoption does not delete
unknown live files; later removal is restricted to previously managed files.
Live drift requires review. Every staged/backup file has its checksum verified.

Each file uses a same-directory atomic replacement with fsync. **The release as a
whole is not atomic.** Only affected previously active services stop during the
multi-file switch. An active KB maintenance job aborts before source changes;
active timers are paused and restored. No package downloads or index work occur
inside the outage. Readiness is scoped to changed services. WhatsApp's connected
business state is monitored separately and does not roll back unrelated code.
Inbox readiness includes the exact locked Send response.

On failure/INT/TERM, affected services stop, journaled source is restored, and
previously active services restart and pass bounded readiness. A concurrent code
edit causes fail-closed rollback instead of overwriting it; rollback failure is
reported explicitly. A hard kill or power loss cannot run traps: retain journals,
inspect them, stop affected services and run the installed helper's `rollback
--journal PATH`, then restart/verify. Never restore the whole application tree.

No journals/releases are automatically deleted until off-host retention and
restore coverage exist. Monitor disk usage. Workflow generation is scoped to the
current verify workflow: resetting/replacing its numbering needs an explicit
reviewed manifest-state migration. Forced downgrade is not exposed to CD.
