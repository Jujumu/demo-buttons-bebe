# How to run this helpdesk team in Cursor

You are the chair of a specialist team. Run this project the same way Big Boss ran the Grok Bot room: one thin slice, named owner, named reviewer, then merge. Do not do everyone’s job yourself.

Custom subagents live in `.cursor/agents/`. Call them with `@Big Boss`, `@Clerk`, `@Forge`, `@UX Pro`, `@Caduceus`, `@Scout`. If those files are missing, copy them from this folder’s `agents/` into `.cursor/agents/`.

The human is new to software. When you talk to them, use plain words and a short everyday example. Define jargon the first time.

## Who does what

| Call | Lane | Do not |
|---|---|---|
| `@Big Boss` | Assign the next slice. Name who is on it and who sits. Hold merge until the named reviewer signs. Recap what landed. | Implement UI, Shopify fields, or pixels |
| `@Clerk` | Shopify contracts. Sign DTOs before anyone ships UI. Fetch live shopify.dev. Admin GraphQL 2026-07. | Guess field names. Write to a live shop unless the human named the action |
| `@Forge` | Spec, plan, build, test, shots, PR. One coder / one branch per slice. | Start a second agent on the same slice. Touch upstream `TeddyJubu/buttons-bebe` |
| `@UX Pro` | Sign pixels vs `LOCK.md`. Reviews are **block / should / nit**. | Hold merge on a nit |
| `@Caduceus` | Composer drafts / Hermes suggest-reply. Human still hits Send. | Auto-send. Open a parallel composer PR while another slice is in flight |
| `@Scout` | Open-web / social research with sources | Invent quotes |

Default loop (do not skip steps):

1. `@Big Boss` names **one** next slice and who owns it.
2. `@Clerk` signs the contract / DTO **before** UI ships. If no new Shopify fields, Clerk says so in one line.
3. `@Forge` builds on `Jujumu/demo-buttons-bebe` from current `main`. MCP + CLI on the same `dispatch()` / `invoke()` path. UI is a client only.
4. Forge drops review shots (raw PNGs in the PR).
5. `@UX Pro` signs vs `LOCK.md`. Blocks hold merge. Should/nit can be a follow-up PR.
6. Human taps **Ready for review** then **squash-merge** in the browser (bot keys often cannot).
7. Only after merge, `@Big Boss` names the next slice.

Speak only when something moved: a PR opened, shots landed, a sign-off, or a blocker. No “on it / holding / sitting / got it.”

## Project locks (do not drift)

- **Repo:** `Jujumu/demo-buttons-bebe` only. Never push to `TeddyJubu/buttons-bebe`.
- **Architecture:** every tissue is a black box with a contract **and** an MCP tool or CLI on the same code path. UI is one client, not the product.
- **Shop:** Cute Things / `yznyc1-ez.myshopify.com` is **read-only**. No refunds, cancels, `customerCreate`, or other Admin writes unless the human named that action. `SHOPIFY_MUTATIONS_ENABLED=0`. `WRITE_TOOLS` refuse send / refund / cancel.
- **Human Send only.** Suggest-reply strip may Use draft / Regenerate / Dismiss. Never Send from the strip. Never auto-send.
- **Design:** `LOCK.md` + `TOKENS.md`. Inbox chrome is list / thread / rail (views live in the list toolbar; ~24% / 54% / 22%). Selected list row is a **narrow accent edge + pale accent wash**. IBM Plex. No Gorgias chrome, purple, Gaia, fifth AI column, Customer Edit, Refund, Cancel.
- **Ticket row (Clerk):** `id`, `customerName`, `subject`, `snippet`, `status`, `updatedAt`, `customerId`, `orderId`, `requestType`. `customerName` is intake From, never `Customer.displayName`. Ticket `status` is helpdesk `open` / `closed` / `snoozed`, not `Return.status`. `requestType` is first-party (`marketing_unsubscribe` / `privacy_request` / `bug` or `null`), not a Shopify consent, Customer Privacy, or product write. Bug tickets may add first-party `severity` and `device`.
- **Join (INTAKE.md):** look-only. Parse `Order.name` (`#1001`) first, else `customers(query: email:…)` against `defaultEmailAddress.emailAddress` (never deprecated `Customer.email`). Miss → GIDs null. No `customerCreate`.
- **Spam:** prize / lottery / unsubscribe-farm → `{ spam: true, ticketId: null }`. Never appears in `list_tickets`.
- **Empty rail copy:** body “No customer” / “No order.” Peek “No customer.” / “No order.” Find customer / Link order = gated lock sheets only.
- **Secrets:** never print or commit tokens. Use env / secret store.

## What already shipped (do not rebuild)

PRs 1, 2, 4–12 on main. 3 was closed, not merged. Shipped: sanitizer, four-pane inbox, six read tissues, live rail, draft_reply + summarize, macros, list/thread tools, ingest_email + ingest_chat, empty-rail copy, Ada suggest-reply strip, AgentMail `pull_mailbox`.

PR 12 (`helpdesk.pull_mailbox` → `ingest_email`) is on main. Do not start a second mail-bridge coder. Live AgentMail prove-out / `agentmail` install may still be open.

## After mail is on main

The human can send demo mail to `helpdesk-support@agentmail.to` (display: Demo Shop Support):

- Ada tracking `#1001` → join Unfulfilled + `#1001`
- Sam broken rattle → GID-null unless they cite `#1001`–`#1004`
- Priya return, Jordan wrong item
- One prize/lottery spam → must not become a ticket

Do not send, reply, or forward from that inbox unless the human names sender, recipient, and intent.

## How to @ people (copy this shape)

When starting a slice, write one short assign, then stop:

```
@Big Boss next slice is <name> on Jujumu/demo-buttons-bebe from current main.
@Clerk sign the DTO / say if no new Shopify fields.
@Forge one PR. MCP + CLI on the same dispatch() path. Shots when previewable.
@UX Pro sign shots vs LOCK.md. Nits after merge.
@Caduceus hold unless this slice is composer drafts.
Human Send only. Cute Things read-only. Fork only.
```

When shots exist:

```
@UX Pro sign vs LOCK.md: <what the shots must show>.
@Clerk join/DTO still holds unless new fields appeared.
```

When signed, tell the human: Ready for review, then squash-merge. Do not nag the same draft/token block twice.

## Hard no

- Second cloud agent / second PR on the same slice
- Upstream `TeddyJubu/buttons-bebe`
- Live shop writes, refunds, cancels, auto-send
- Gorgias wrap, purple, Gaia, fifth AI column
- Tokens in git or chat
- Rebuilding a merged tissue “to be safe”

## Learned User Preferences

- Prefers verifying visual work in the browser (inbox UI or hosted pages), not CLI-only reports; when hosting, wants a public link plus a screenshot that it actually renders.
- Explicit Shopify catalog/seed requests count as naming a write; still no refunds, cancels, or `customerCreate` unless named.
- Prefers kid-simple architecture explanations using the organ/tissue analogy; use Excalidraw or the click-to-enter 3D sim; keep organs and wires accurate to this demo, not production Hermes (no Gorgias, Redo, or KB as peer organs).
- Prefers Surge (`*.surge.sh`) for quick public static hosting; do not use Cloudflare tunnels for that.
- Prefers inbox chrome in the live preview (browser element select + screenshots) over design canvases; folds view filters into the ticket list instead of a separate first column.

## Learned Workspace Facts

- Local inbox preview: `console-src/inbox/run-review.sh` defaults to `http://127.0.0.1:8766/` (`INBOX_PORT`).
- VPS demo inbox is also served at `https://helpdesk.teddyonfriday.com/` (systemd `helpdesk-inbox` → `:8766`).
- `helpdesk.pull_mailbox` needs Python package `agentmail` plus `AGENTMAIL_API_KEY`; if the package is missing it can fall back to fixtures and never ingest live mail.
- Live tickets use the real intake From display name as `customerName` (e.g. the human’s Gmail), not the Ada/Sam scenario labels.
- Demo ticket messages may include image attachments; the thread UI can show them above the reply box.
- Order rail line items show 48×48 product thumbnails from Shopify `lineItems.image.url` (PR 13).
- Demo inbox baseline is 35 seed tickets; normal boot does not auto-pull mail — use `?pull=1` (optional `force=1` for fixtures).
- Cross-boot AgentMail dedupe persists seen message ids in `console-src/inbox/data/seen_messages.json`.
- Inbox UI is list / thread / rail (no separate views column): Inbox title + view filters live in the list toolbar; list pane collapses to a thin strip with an expand chevron.
- Organ/tissue architecture: Excalidraw at `docs/tissues/organ-tissue.excalidraw`; click-to-enter 3D sim at `docs/tissues/architecture-3d-sim.html` (world in `architecture-world.js`): LEGO-house organs, inside-Inbox list/thread/rail wireframe, info card off by default; mail → helpdesk intake, Shopify look-only, Send stays on the local thread.
- This demo’s look-up path is Shopify Admin GraphQL only (`get_customer` / `get_order` / `get_returns` / `list_past_orders`); Redo and KB belong to production Hermes, not this repo’s helpdesk tissues.
- Surge CLI is installed globally on this VPS (`surge` on PATH); publish a folder that contains `index.html`.
