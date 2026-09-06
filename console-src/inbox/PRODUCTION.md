# Isolated inbox runtime

This service remains a read-only side room. The existing console and Gorgias
intake are the operational system. The inbox API exposes ticket reads, status,
a capability document, and an unconditionally locked Send response. It does not
expose intake, external providers, drafts, escalation, or handled-state writes.
Disabled capabilities are hidden in the interface and refused by the server.

## Runtime

Python 3.12 or later; install `requirements.txt` into a dedicated virtualenv.
`run-review.sh` accepts `INBOX_PYTHON`, binds only 127.0.0.1, and defaults to port
8766. It forcibly disables outbound, bridge and Shopify mutations. The server
never loads `.env` files. Caddy must authenticate **every** inbox path, strip the
`/inbox` prefix, and proxy both static assets and `/console/api/helpdesk` to this
service. Never intercept the old console API to make this work.

Use a dedicated unprivileged service account, restrictive umask and a writable
`/var/lib/buttonsbebe-inbox` directory. `HELPDESK_DB_FILE` defaults to
`/var/lib/buttonsbebe-inbox/inbox.sqlite3`. Keep this directory outside code
releases and never replace it during rollback. Runtime code, dependencies and
`static-manifest.json` must be read-only to the service account. The manifest is
an explicit public-asset allowlist; fixtures, source Python and data are absent.

The ASGI server has bounded connection concurrency, body size and body-read
time. Exposed API tools perform local operations only. Static responses set
no-store, a restrictive CSP, nosniff and same-origin referrer policy. Logs omit
request contents and query strings. Caddy remains responsible for identity and
access control; a loopback connection is not an authenticated human identity.

## Legacy migration

Before changing the service account/runtime, inspect whether the old inbox data
directory contains ticket or seen JSON files. If present, stop the old inbox,
back up the originals securely, then run as an operator able to read that path:

```
python console-src/inbox/migrate_store.py \
  --tickets /absolute/old/data/intake_tickets.json \
  --seen /absolute/old/data/seen_messages.json \
  --database /var/lib/buttonsbebe-inbox/inbox.sqlite3
```

The target must not already exist. The importer validates state, commits it in
one SQLite transaction and retains the originals. Invalid/corrupt records fail
visibly, rather than being skipped or replaced with an empty inbox. A seen-only
legacy store is refused until reconciled. Change directory/database ownership
to the dedicated service account before starting the new runtime. When no
legacy state exists, startup creates an empty database; it never adds demos.
The server ignores legacy JSON environment settings, so it cannot accidentally
read stale root-owned files after migration.

## Durability and limits

SQLite stores a versioned whole-inbox snapshot. `BEGIN IMMEDIATE` serializes
read/modify/write operations across processes, reloads the committed state, and
commits tickets, deduplication IDs and the sequence together. Failed operations
roll back and refresh the in-memory cache. WAL and FULL synchronization protect
committed state. Startup/readiness fail visibly on corruption. Existing local
workflow helpers now persist flags, but they are not exposed as production
capabilities because no corresponding owner/customer workflow is connected.

This is suitable for the current small isolated store, not a claim of unlimited
throughput: full snapshots scale with retained history. Before adding real
intake, define retention, measure representative state size and migrate to
normalized ticket/message/action tables if needed. Back up through SQLite's
backup API; do not copy a live database file without its transaction state.
Future real intake must use one outer `tickets.transaction()` covering both
remembering the message and creating its ticket. Do not expose individual
helpers as separate intake API operations.

## Verification

```
python -m unittest discover -s console-src/helpdesk-agent/tests
node --test console-src/inbox/test/*.test.js
# Runtime Python needs httpx for this test, not for production serving.
python console-src/inbox/test/test_review_server.py
```

Tests cover restart persistence, operation/commit failure, simultaneous writers,
legacy/corrupt state, malformed JSON types, oversized bodies, static traversal
and symlinks, unsupported capabilities, UI failure behavior, and the Send lock.
The HTTP Send response must retain `send_access_inactive` and exactly
`Activate the send access.`. Inbox `/webhook/gorgias` must return 503.
