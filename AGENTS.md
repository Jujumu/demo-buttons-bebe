# AGENTS.md — Buttons Bebe AI Support Agent

> Reflects the live system as of **2026-07-14**. `CLAUDE.md` is the co-source of
> truth for deep architecture; this file is the operational map for agents.
> Any doc describing `/root/gorgias-webhook`, "shadow mode", Supermemory/ChromaDB,
> an 8-tool `hermes-tools-mcp`, or the "Mimo" model describes a **retired** system
> (box wiped & rebuilt 2026-07-06). `_VPS-FULL-BACKUP-20260706/` holds plaintext
> secrets — gitignored, never commit or restore from it.

## 1. What & why

AI support agent for **Buttons Bebe** (Shopify store, ~2k tickets/month in
**Gorgias**). Per incoming ticket: read message → pull order/return/product
context → search KB → draft a reply **into the review console** (not into
Gorgias) where a human sends / notes / edits / discards. Client: **Chaim**.

## 2. Safety model (never violate)

1. Hermes never sends a customer reply and never writes to Gorgias — it only
   returns draft text.
2. Hermes + its three MCP tools are strictly READ-ONLY (Gorgias read, Redo
   read, KB search). No credential loading, no direct API/curl fallbacks.
3. The only external writes are human-triggered console actions:
   `POST /dashboard/api/ticket/{id}/send|note|rewrite` on the webhook app
   (:8000). Publicly reached via Caddy Basic-Auth as `/console/api/*`; direct
   public `/dashboard*` access is denied. Send requires a confirm click;
   rewrite returns text to the console and never sends it.
4. Every ticket gets a draft. Sensitive tickets (refunds, chargebacks,
   disputes, damaged/wrong/missing items, cancellations, angry customers) get
   a clearly prefixed sensitive draft, HIGH/CRITICAL priority, and an owner
   alert. The human remains the safety gate.
5. Jobs, results, alerts, and learning actions are all logged.

## 3. Where it runs

- Production: VPS **`srv1766050`** (2.25.137.77), Ubuntu, everything under
  `/root/Buttonsbebe Agent/`. This repo mirrors that tree.
- Brain: **Hermes Agent** CLI (Nous Research), model **`glm-5.2`** via Ollama
  Cloud (`~/.hermes/config.yaml`).
- **A push to `main` that passes CI auto-deploys to production** — see §8.

## 4. End-to-end flow

```text
Gorgias webhook
  → bb_webhook FastAPI :8000        HMAC verify (WEBHOOK_SECRET), dedupe
  → SQLite job_queue                webhook/data/webhook.db (WAL)
  → buttonsbebe-processor           polls ~every 2s, one Hermes run per job
  → hermes -t mcp-buttonsbebe_kb,mcp-buttonsbebe_redo,mcp-buttonsbebe_gorgias -z "…"
       ├─ buttonsbebe_gorgias :8079   ticket / messages / customer (read-only)
       ├─ buttonsbebe_redo    :8078   return & refund status (read-only)
       └─ buttonsbebe_kb      :8077   LanceDB hybrid search: policies · faq ·
                                      intents · products · tickets
  → <DRAFT:{token}>…</DRAFT> extracted, cleaned (draft_cleaner.py), stored in
    ticket_results, shown in the console Ticket feed
  → HUMAN clicks Send reply / Draft as internal note / Request edit (or ignores)
```

- Hermes always reports `gorgias_priority_set=false`, `note_posted=false`. The
  processor may WhatsApp-alert the owner for HIGH/CRITICAL work but never
  writes Gorgias.
- `processor/gorgias_writer.py` still defines `post_internal_note()` but
  nothing calls it — dormant. Do not re-wire without revisiting the safety
  model.
- Prompt-injection hardening lives in `hermes_runner.py`: run-token
  `<DRAFT:token>` tags prove the draft is Hermes'; customer-supplied
  `<DRAFT>` blocks are neutralised and fail closed. Don't loosen casually.
- Toolsets are an explicit allow-list (`HERMES_TOOLSETS` in
  `processor/config.py`, built in `build_hermes_command()`), never `--yolo`
  (`HERMES_SKIP_APPROVAL=1` is a temporary unblock only). A misspelled
  toolset name silently drops the tool instead of erroring — run
  `tools/verify_hermes_toolset.sh` on the VPS after changing either.

## 5. Components (repo dirs)

| Dir | What |
|---|---|
| `webhook/` | FastAPI receiver + queue DB + console API (`src/bb_webhook/app.py`). uv package. |
| `processor/` | Orchestrator loop; `hermes_runner.py` (prompt, command build, draft extraction); `draft_cleaner.py`; `whatsapp_notifier.py`; `heartbeat.sh`. uv package. |
| `kb/` | KB markdown (`intents/ faq/ policies/ tickets/ products/ shopify/` — `shopify/` is shopify.dev platform background), LanceDB index/sync scripts, MCP server, systemd units/timers, `search.sh`. |
| `tools/` | Read-only Redo + Gorgias MCP modules, `run-gorgias.sh` / `run-redo.sh`, `verify_release.sh`, `verify_hermes_toolset.sh`. |
| `kb-admin/` | KB editor API (Node, :8087) with auth-safety tests. |
| `whatsapp-connect/` | Node + Baileys: QR pairing page, owner alerts, 2-way Hermes bridge (:8085). |
| `console-src/index.html` | **THE** console SPA source (includes Notice Board tab); deployed to the web root by CD. |
| `dashboard/index.html` | Older console snapshot without Notice Board — superseded, kept for reference. |
| `deploy/` | Only supported Caddy config (`caddy/Caddyfile.redacted`), CD receive script (`cd/`), systemd units, ENV-consolidation + heartbeat runbooks, tests. |
| `testing/` | 48-scenario suite (`scenarios.json`), TEST-PLAN, judging rubric, HOW-TO-RUN. |
| `feedback/` | PII masking library + retired-poller tests. |
| `fable/` + branch `Fable_buttonsbebe` | Track B standalone prototype — quarantined background, **not** planned work. |
| `hermes/` | In-repo copies of `SOUL.md` + `skills/buttonsbebe`; `config.example.yaml` is a template (real `config.yaml` is gitignored). |

## 6. Services & ports (all bind localhost)

| Port | Service | systemd unit |
|---|---|---|
| 8000 | Webhook receiver + console API (uvicorn) | `buttonsbebe-webhook` |
| 8077 | KB MCP — `search_kb` | `buttonsbebe-kb-mcp` |
| 8078 | Redo MCP | `buttonsbebe-redo-mcp` |
| 8079 | Gorgias MCP | `buttonsbebe-gorgias-mcp` |
| 8085 | WhatsApp connect (QR + alerts + bridge) | `buttonsbebe-whatsapp-connect` |
| 8087 | KB admin API | `buttonsbebe-kb-admin` |
| — | Job processor | `buttonsbebe-processor` |
| — | Timers: product sync (3d) / notices GC / nightly learn (03:30) | `buttonsbebe-kb-sync` / `-notices-gc` / `-kb-learn` |

Caddy (`deploy/caddy/Caddyfile.redacted` is the only supported source;
`webhook/Caddyfile` is marked RETIRED): Basic-Auth console at `/console/*`
(rewritten internally to `/dashboard/api/*`; `/console/kbapi` → :8087,
`/console/waapi` → :8085); public allowlist is only `/webhook/gorgias/*`,
`/health`, `/ready`, `/connect-whatsapp/*`; everything else 404s.

## 7. Credentials

One root `.env` (consolidated 2026-07-08): both `processor/config.py` and
`webhook/src/bb_webhook/config.py` load it. `webhook/.env` is legacy, pending
removal on the VPS — do not add values there; see
`deploy/ENV-CONSOLIDATION-RUNBOOK.md`.

Shopify = client-credentials grant (`SHOPIFY_CLIENT_ID/SECRET`, mint 24h Admin
token); Gorgias = Basic (email + API key); Redo = Bearer. Never commit `.env*`
or anything from `_VPS-FULL-BACKUP-*/`. Hermes skills never read env files —
the authenticated MCP services are their only runtime data path.

## 8. Verify before pushing — CI auto-deploys `main`

Pushing to `main` runs the `verify` workflow and, on success,
**auto-deploys that commit to production**
(`.github/workflows/deploy-production.yml`). Run the identical offline gate
first:

```bash
bash tools/verify_release.sh   # needs ripgrep + node; set PYTHON/PROCESSOR_PYTHON to prepared venvs
```

Gate facts (each exists because something slipped once):

- Syntax-checks first-party Python under `feedback kb processor testing tools
  webhook deploy` and asserts ≥40 files parsed, so a broken skip-list fails
  loudly instead of passing on nothing.
- Auto-discovers every `processor/test_*.py`; exclude a live-VPS diagnostic
  with the marker line `# offline-gate: skip` (`test_e2e.py` hits a real VPS
  this way).
- Runs unittest suites in `kb/tests`, `deploy/tests`, `tools.test_tool_contracts`,
  webhook notification tests, feedback tests; `node --test` for
  whatsapp-connect security tests and kb-admin.
- **Fails on any active `twilio` reference** — escalation is the local
  WhatsApp bridge now; do not reintroduce Twilio.
- Enforces exactly **48** unique-id scenarios in `testing/scenarios.json`.

Focused runs:

```bash
(cd processor && uv run python -m unittest test_draft_cleaner -v)
(cd processor && uv run python -m unittest discover -p 'test_*.py' -v)
(cd whatsapp-connect && npm test)
```

Python ≥ 3.12, uv-managed (`uv.lock` in `processor/`, `webhook/`); Node 20 for
JS services. A clean 48-scenario live-model run is the release-quality gate —
see `testing/HOW-TO-RUN.md` before any behavior-changing deploy.

## 9. Operate on the VPS

```bash
hermes mcp list && hermes mcp test buttonsbebe_kb
systemctl status buttonsbebe-processor buttonsbebe-kb-mcp buttonsbebe-redo-mcp \
  buttonsbebe-gorgias-mcp buttonsbebe-kb-admin
journalctl -u buttonsbebe-processor -n 50
cd "/root/Buttonsbebe Agent/KB" && ./search.sh "do you ship to canada"
./sync-products.sh                     # manual product refresh (else every 3 days)
sqlite3 "/root/Buttonsbebe Agent/webhook/data/webhook.db" \
  "select status,count(*) from job_queue group by status"   # table is job_queue, not jobs
```

## 10. Live vs retired code, and which docs to trust

**Live:** the whole pipeline above; learning loop (every console action →
`KB/learned/lesson-*.md` via `webhook/src/bb_webhook/learning.py`; nightly
PII-masked promotion to indexed `KB/tickets/exemplar-learned-*.md` + index
rebuild); Notice Board override layer (immediate effect, no reindex; GC timer
purges expired notices); heartbeat dead-man's switch (`processor/heartbeat.sh`,
`deploy/HEARTBEAT-INSTALL.md`); KB admin (:8087).

**Retired but present — fail-closed; don't "fix" them back to life:**

- `processor/classifier.py` — advisory deterministic rules only; Hermes also
  classifies; the processor can raise priority but never lower it.
- `processor/feedback_collector.py` — superseded poller; rollback only via
  `FEEDBACK_LEGACY_OPT_IN=1` for a bounded test.
- `processor/gorgias_writer.py` — dormant (§4).

**Doc trust order:** `CLAUDE.md` ≈ this file → `HANDOVER/` (good onboarding,
but dated 2026-07-13 *before* the Fable port: its "webhook/processor source is
not in the repo" claims are outdated) → `PORTFROMFABLETASKLIST.md`,
`IMPROVEMENT-PLAN.md`, `TESTING-READINESS.md` (context). **Superseded — do not
implement from:** `INCONSISTENCIES.md`, `DEV-ISSUES.md`. **Stale layout:**
root `README.md` (describes the retired `gorgias-webhook/` + `teddy/` design).
