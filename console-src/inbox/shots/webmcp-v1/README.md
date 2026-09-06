# WebMCP v1 — verify notes

## Flag

1. Chrome → `chrome://flags/#enable-webmcp-testing` → **Enabled** → relaunch.
2. Open the inbox (local review or VPS).
3. Install / open the Model Context Tool Inspector (or call `document.modelContext.getTools()` in DevTools).

## URL

- Local: `http://127.0.0.1:8766/` via `console-src/inbox/run-review.sh`
- VPS: `https://helpdesk.teddyonfriday.com/`

## Tools registered (Document-scoped; not `helpdesk.*`)

| Tool | Organ API | Notes |
|---|---|---|
| `select_view` | `organ.selectView` | viewId enum |
| `select_ticket` | `organ.selectTicket` | ticketId |
| `use_draft` | `organ.insertDraft` | Ada strip — no Send |
| `regenerate_draft` | `organ.regenerateDraft` | Ada strip — no Send |
| `dismiss_draft` | `organ.discardStrip` | Ada strip — no Send |
| `summarize_thread` | `organ.requestSummarize` | optional, included |
| `open_macros` | `organ.openMacros` | optional, included |
| `apply_macro` | `organ.applyMacro` | optional, included |

**Hard omit:** any Send / reply-send / refund / cancel WebMCP tool.

## Progressive enhancement

Without the flag, `document.modelContext` is missing — registration is a no-op and the inbox works for humans as before.

## Shots

Raw PNGs in this folder prove list/thread/rail chrome unchanged and Ada strip Use / Regenerate / Dismiss. After an agent-style `select_ticket` (via `globalThis.__inboxOrgan.selectTicket` — same path WebMCP `execute` calls), the selected row keeps the narrow accent edge + pale wash.

| File | What it shows |
|---|---|
| `01-chrome-ada-strip.png` | List / thread / rail + Ada strip buttons |
| `02-before-select.png` | Starting selection before agent select |
| `03-after-select-ticket-accent.png` | After `selectTicket("t-ada-track")` — accent holds |
| `verify.json` | Headless checks (WebMCP flag off → `available: false`) |

Automation cannot enable `chrome://flags/#enable-webmcp-testing`; use the flag + Tool Inspector locally to list/invoke tools.
