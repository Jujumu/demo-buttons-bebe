# CLAUDE.md — Buttons Bebe AI Support Agent

> Current production architecture as of 2026-07-14. Older notes describing
> Supermemory/ChromaDB, Mimo, `/root/gorgias-webhook`, autonomous Gorgias notes,
> or direct Shopify API tools are retired.

## Purpose

The service reads incoming Gorgias tickets, gathers read-only order/return and
product context, searches the knowledge base, and creates a reply draft in the
console. A human reviews every draft and chooses whether to send it publicly,
post it as an internal note, request a rewrite, or discard it.

## Non-negotiable safety model

1. Hermes never sends a customer reply or posts an internal note.
2. Hermes and its three MCP tools are read-only: Gorgias read, Redo read, KB
   search. Hermes must not load credentials or use direct API/curl fallbacks.
3. Gorgias writes exist only behind human-triggered, signed-session-protected
   console endpoints: `POST /console/api/ticket/{id}/send|note|rewrite`. The
   standalone `/console/login` page issues an HttpOnly session cookie; Caddy's
   `forward_auth` check gates the console, WhatsApp, KB-admin, and dashboard API
   routes. Caddy rewrites these internally to the FastAPI `/dashboard/api/*`
   namespace; direct public access to `/dashboard` and `/dashboard/*` is blocked.
   Public send requires a confirmation click; rewrite returns text to the console
   and does not send it.
4. Every ticket gets a draft. Sensitive tickets (refunds, disputes,
   damaged/wrong/missing items, cancellations, angry customers, and similar)
   get a clearly prefixed sensitive draft, HIGH/CRITICAL review priority, and
   an owner alert. The human remains the safety gate.
5. Shopify, Redo, and normal Gorgias access are read-only. The only external
   writes are human-initiated Gorgias send/note actions.
6. Jobs, results, alerts, and learning actions are logged.

## Live flow

```text
Gorgias webhook
  -> bb_webhook FastAPI :8000
  -> SQLite job_queue (webhook/data/webhook.db, WAL)
  -> buttonsbebe-processor
  -> one-shot Hermes (glm-5.2 via Ollama Cloud)
       -> buttonsbebe_gorgias :8079 (read-only)
       -> buttonsbebe_redo    :8078 (read-only)
       -> buttonsbebe_kb      :8077 (read-only hybrid search)
  -> draft stored in ticket_results and shown in the console
  -> human may Send reply / internal Note / Request edit
```

Hermes returns `<DRAFT>...</DRAFT>` and a `JSON_RESULT`. It always reports
`gorgias_priority_set=false` and `note_posted=false`. The processor may send an
owner alert through the local WhatsApp bridge for HIGH/CRITICAL work, but it
does not write to Gorgias.

## Knowledge base

- Live root: `/root/Buttonsbebe Agent/KB`
- Sources: `intents/`, `faq/`, `policies/`, `tickets/`, `products/`, and
  lower-trust Shopify platform background in `shopify/`
- Index: LanceDB hybrid vector + FTS search
- Product source: active Shopify catalog, refreshed every three days by
  `buttonsbebe-kb-sync.timer`
- Product sync stages and validates the catalog, holds the sync/index locks
  through rebuild, restores the previous corpus on failure, and promotes a new
  index only after exact content validation.
- Search readers hold a shared promotion lock, so they see the previous or the
  new complete index, never a partial swap.
- `learned/` stores raw console lessons and is never indexed. Nightly promotion
  masks PII and writes confirmed `source: learned-auto` exemplars to `tickets/`.
- The Notice Board is a locked, immediate override layer and requires no
  reindex. Expired notices are removed by `buttonsbebe-kb-notices-gc.timer`.

## Services

| Port | Service | systemd unit |
|---|---|---|
| 8000 | Webhook receiver + dashboard API | `buttonsbebe-webhook` |
| 8077 | KB MCP | `buttonsbebe-kb-mcp` |
| 8078 | Redo MCP | `buttonsbebe-redo-mcp` |
| 8079 | Gorgias MCP | `buttonsbebe-gorgias-mcp` |
| 8085 | WhatsApp connect/alerts | `buttonsbebe-whatsapp-connect` |
| 8087 | KB admin API | `buttonsbebe-kb-admin` |
| — | Queue processor | `buttonsbebe-processor` |

Caddy exposes the session-protected support console at
`https://srv1766050.hstgr.cloud/console/`; all application services bind to
localhost. The internal `/dashboard/*` namespace is explicitly blocked. The
public Caddy allowlist includes only the login/auth paths needed to establish a
session, `/webhook/gorgias/*`, `/health`, and `/ready`; all other unmatched paths
return 404. Console data and writes still require a valid session cookie.

## Learning loop

Every human console action writes a unique `lesson-*.md` packet and updates the
learning ledger under a lock. At 03:30 UTC, `buttonsbebe-kb-learn.timer` masks
known names and identifier patterns, promotes distinct exemplars, and rebuilds
the KB. PII masking is best-effort; generated exemplars remain reviewable and
purgeable.

## Credentials

- `/root/Buttonsbebe Agent/.env`: Gorgias/Shopify/Redo credentials for server
  modules and maintenance scripts.
- `/root/Buttonsbebe Agent/webhook/.env`: **legacy**. The webhook and processor
  both read the root `.env` now; this file is pending removal on the VPS
  (`deploy/ENV-CONSOLIDATION-RUNBOOK.md`).
- Hermes skills must never read either file. The authenticated MCP services are
  the only runtime data path for Hermes.

## Known limitations

- `processor/classifier.py` remains an advisory deterministic classifier; Hermes
  also classifies, and the processor can only raise sensitive priority.
- `processor/feedback_collector.py` is a fail-closed retired poller. The live
  learning path is console action capture in `webhook/.../learning.py`.
- Environment values: the CODE is consolidated — `processor/config.py` and
  `webhook/src/bb_webhook/config.py` both read the single root `.env` (since
  2026-07-08). What remains is the VPS-side merge of the leftover
  `webhook/.env` and rotating the credentials that sit in plaintext in
  `_VPS-FULL-BACKUP-20260706/`. Step-by-step:
  `deploy/ENV-CONSOLIDATION-RUNBOOK.md`. No secret has ever been committed to
  git (full-history prefix scan, 2026-07-29).
- Hermes runs with an explicit tool allow-list, not `--yolo`. The processor
  passes `-t buttonsbebe_kb,buttonsbebe_redo,buttonsbebe_gorgias`
  (see `build_hermes_command()` in `processor/hermes_runner.py`), so the
  `terminal` and `file` toolsets are out of scope and there is nothing
  dangerous left to auto-approve. Override with `HERMES_TOOLSETS`;
  `HERMES_SKIP_APPROVAL=1` puts `--yolo` back as a temporary unblock only.
  Run `tools/verify_hermes_toolset.sh` on the VPS after changing either — a
  misspelled toolset name silently drops the tool instead of erroring.

## Verification

```bash
hermes mcp list
hermes mcp test buttonsbebe_kb
systemctl status buttonsbebe-processor buttonsbebe-kb-mcp \
  buttonsbebe-redo-mcp buttonsbebe-gorgias-mcp buttonsbebe-kb-admin
cd "/root/Buttonsbebe Agent/KB" && ./search.sh "do you ship to canada"
sqlite3 "/root/Buttonsbebe Agent/webhook/data/webhook.db" \
  "select status,count(*) from job_queue group by status"
```

## Background reading

Ported from the `Fable_buttonsbebe` branch on 2026-07-29. **Track A** in these
documents is the live system described above; **Track B** is Fable, a
standalone help-desk prototype that stayed on its branch and is not part of
`main`. Treat Track B material as background, not as planned work.

| Document | What it is |
|---|---|
| `PORTFROMFABLETASKLIST.md` | The port itself — what came across from Fable, what deliberately did not, and the status of each task. Start here. |
| `IMPROVEMENT-PLAN.md` | The reasoning behind the reliability and quality work (draft cleaner, heartbeat, classifier coverage, one `.env`). |
| `DESIGN-CRITIQUE.md` | Code-level review of the console and the old dashboard. |
| `TESTING-READINESS.md` | Defines "ready to ship": a clean 48-scenario run is the gate before any live change. |
| `Buttons-Bebe-Competitive-Brief.html` | Point-in-time market snapshot. Background only. |
| `testing/TEST-PLAN.md` · `testing/HOW-TO-RUN.md` | The 48 scenarios, the A–E rubric, and how to run them against the live model. |
| `deploy/HEARTBEAT-INSTALL.md` | Installing the dead-man's switch on the VPS. |
| `deploy/ENV-CONSOLIDATION-RUNBOOK.md` | Merging the two `.env` files and rotating secrets. VPS work, not yet done. |

Deliberately **not** ported: `SPRINT-2-PLAN.md` and `CONTINUE-HERE.md` are
finished-sprint logs specific to the Fable branch — on `main` they would read
as current work.
