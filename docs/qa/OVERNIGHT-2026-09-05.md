# Overnight code quality report — 2026-09-05

Audited `Jujumu/demo-buttons-bebe` `main` at `e4c18c6` (Privacy request
type, first-party, #27). Scope: helpdesk organ, inbox UI, write gates,
and fixture vs Admin GraphQL **2026-07** field lock.

This is a read-only review. No product redesign. No live Admin write
paths were added. Cute Things stays look-only.

## Verdict

**Write gate holds.** `helpdesk.send` / `helpdesk.refund` / `helpdesk.cancel`
have no handlers. `dispatch()` refuses them before any tissue runs, even
when `SHOPIFY_MUTATIONS_ENABLED=1`. Live GraphQL is query-only
(`assert_query_only` + static documents in `queries.py`). Composer Send
is UI-local and never calls `helpdesk.send`. No `customerCreate`,
consent, marketing-unsubscribe, or Customer Privacy Admin mutations on
the helpdesk path.

**No blocker.** The inbox can ship. The items below are follow-ups.

## Shopify Admin facts (do not invent)

Checked against Admin GraphQL 2026-07 (`Order` object,
`DraftOrder.invoiceUrl`, `giftCard` query, `orderInvoiceSend`).

| Peek | Fixture | Live query today | Official Admin fact |
|---|---|---|---|
| Invoice | `Order.invoiceUrl` string | omitted from `ORDER_QUERY`; DTO returns `null` | **`Order` has no `invoiceUrl`.** `DraftOrder.invoiceUrl` exists. Sending uses mutation `orderInvoiceSend` (write-gated, unused). |
| Warranty | `Order.warranty` `{period,status,endsOn}` | omitted; DTO returns `null` | **`Order` / `LineItem` have no warranty field.** Do not invent a metafield namespace/key. |
| Gift cards | `Customer.giftCards[]` | omitted; DTO returns `[]` | **`Customer` has no `giftCards` connection.** Root `giftCard` / `giftCards` queries exist. LOCK is correct: live stays empty until Clerk wires `giftCards(query: "customer_id:…")`. |
| Shipping zone | `Order.shippingZone` | omitted; DTO returns `null` | **`Order` / `Fulfillment` have no shipping-zone field.** |
| ETA | fixture `eta` or live `Fulfillment.estimatedDeliveryAt` | queried | Official. Empty peek `No ETA`. |
| Discounts | `Order.discountCodes` | queried | Official `[String!]`. |

Join uses `orders(query:"name:…")` then
`customers(query:'email:"…"')` against
`defaultEmailAddress.emailAddress`. No deprecated `Customer.email`. Miss
→ GID null. Ticket `customerName` is intake From, never
`Customer.displayName`. Ticket `status` is `open` / `closed` / `snoozed`,
never `Return.status`.

---

## Blocker

None.

---

## Should

### S1. `mark_privacy_handled` is not on the shared dispatch path

`tickets.mark_privacy_handled()` exists and is first-party (not a Shopify
privacy write). It is **not** in `HANDLERS`. Inbox
`createHelpdeskShop().markPrivacyHandled()` always hits the JS fixture
shop. Live/review inbox “Mark privacy handled” does not persist through
MCP / CLI / `POST /console/api/helpdesk`. Refresh loses the flag.
`escalate_ticket` is wired; privacy is not.

- `console-src/helpdesk-agent/helpdesk/tickets.py` (`mark_privacy_handled`)
- `console-src/helpdesk-agent/helpdesk/tissues.py` (`HANDLERS`)
- `console-src/inbox/js/shop/helpdesk-shop.js` (`markPrivacyHandled`)

**Fix:** Add `helpdesk.mark_privacy_handled` to `HANDLERS` / MCP / CLI
(keep it **out** of `WRITE_TOOLS`). Route the inbox through `invoke()`.
Not a small fix.

### S2. Live join falls back to fixture GIDs after a miss or GraphQL error

`_find_order` / `_find_customer` try live, then always call the Cute
Things fixture catalog. A transient Admin failure, or a real miss on a
live-configured host, can attach fixture GIDs
(`ai-demo-unfulfilled@example.com` → `C_UNFULFILLED` / `#1001`) to a
real inbound message.

- `console-src/helpdesk-agent/helpdesk/join.py` (`_find_order`, `_find_customer`)

**Fix:** Fixture fallback only when live mint is unavailable or
`HELPDESK_SOURCE` is `sample` / `live-holes`. On a live-configured miss,
return `(None, None)`. Needs tests. Not a small fix.

### S3. Numeric alias `1003` points at the wrong ticket

`ALIASES["1003"]` and composer `SAMPLE_RAIL["1003"]` resolve to
`t-jordan-ship` (Canada shipping, no order). The ticket that cites order
`#1003` is `t-casey-throw` (`LIVE_GIDS` maps that id to `O_1003`).
`get-ticket --ticket-id 1003` and `draft-reply --ticket 1003` load
Jordan, not Casey.

- `console-src/helpdesk-agent/helpdesk/tickets.py` (`ALIASES`)
- `console-src/helpdesk-agent/helpdesk/composer.py` (`SAMPLE_RAIL`)

**Fix:** Map `"1003"` → `t-casey-throw`, or drop numeric aliases beyond
`#1001` / `#1002` if they are order-number shortcuts. Add a regression
test.

### S4. Boot view `"open"` is not a sidebar row

`createInboxOrgan` defaults to `"mine"`. `boot.js` overrides to `"open"`.
The views pane only lists `mine` / `unassigned` / `all` / `snoozed` /
`closed`. Backend `list_tickets(view="open")` is valid (all open
tickets), but no view row gets the ink bar and the list header falls
back to `"Inbox"`.

- `console-src/inbox/js/boot.js`
- `console-src/inbox/js/fixtures/demo-inbox.js` (`views`)
- `console-src/helpdesk-agent/helpdesk/tickets.py` (`VIEWS`)

**Fix:** Default boot to `"mine"`, or add an Open row that matches
`ticketInView`. One-line boot change is enough if UX wants Assigned-to-me
as the home view.

### S5. `pull_mailbox` ingested rows dropped `requestType`

`list_tickets` / `get_ticket` / `ingest_email` emit Clerk row
`requestType`. `mailbox._ticket_row()` stripped it, so
`helpdesk.pull_mailbox` consumers missed Unsubscribe / Privacy chips
until a follow-up `get_ticket`.

- `console-src/helpdesk-agent/helpdesk/mailbox.py` (`_ticket_row`)

**Fix in this PR:** keep `requestType` on the ingested row. Test added.

### S6. Missing `shopMoney` on a line item 500s the whole order rail

`line_item()` always calls `money_v2(shop_money)`. Fixture catalogs are
complete. A live node with a missing `originalUnitPriceSet.shopMoney`
raises `bad_request` and blanks This order.

- `console-src/helpdesk-agent/helpdesk/dto.py` (`line_item`)

**Fix in this PR:** omit `originalUnitPriceSet` when `shopMoney` is
absent. Test added.

### S7. Gate copy always says the flag “stays 0”

Writes stay refused when the flag is `1` (correct, fail-closed).
`forbidden_write` / `write_gate_status` still say
`SHOPIFY_MUTATIONS_ENABLED stays 0.` while `details.mutationsEnabled`
may be `true`. Ops can misread the gate.

- `console-src/helpdesk-agent/helpdesk/errors.py`
- `console-src/helpdesk-agent/helpdesk/tissues.py` (`handle_write_gate_status`)

**Fix:** Message should say writes are refused regardless of the flag,
until a named human write exists. ~5 lines.

### S8. Catalog seed script is a live Admin write outside the helpdesk gate

`tools/seed_demo_products.py` runs `productCreate` /
`productVariantsBulkUpdate` / `publishablePublish` with no
`SHOPIFY_MUTATIONS_ENABLED` check and no `dispatch()` path. Accidental
run writes to Cute Things. Not inbox runtime.

**Fix:** Refuse `main()` unless an explicit confirm env is set. Document
as human-only. Do not add that write path to helpdesk tools.

### S9. A11y gaps on composer and gate sheets

- Reply `<textarea>` has placeholder only — no name.
  `console-src/inbox/js/tissues/composer.js`
- AI draft strip and summarize peek have no `aria-live`. Same file.
- Privacy / payments dialogs set `role="dialog"` / `aria-modal` but do
  not move focus, trap Tab, restore focus, or handle Escape.
  `console-src/inbox/js/inbox.js`
- Ticket and view lists are click-only button groups (`role="list"`
  without `listitem`; `aria-current="false"` on every idle row).
  `console-src/inbox/js/tissues/list.js`, `view.js`

**Fix:** Name the textarea; polite live region on the strip; focus +
Escape on sheets; drop invalid list roles. Keyboard roving is a later
slice.

### S10. Returns peek can say “In transit” while the body omits tracking

Ada `#1001` fixture return peek uses `record.tracking`. Expanded body
shows items, `Status Open`, and refund/credit only. `DEMO-RET-1001` is
dropped. `Status Open` also collides with ticket status “Open”.

- `console-src/inbox/js/tissues/returns.js`

**Fix:** Render carrier + mono number + Track when `tracking` exists
(reuse shipment chrome). Label return status `Return status`. Not a
small fix.

---

## Nit

### N1. `clerk_returns` assumed every return node is a dict

Malformed GraphQL `returns.nodes` would `AttributeError` instead of a
structured skip. Same file already guards fulfillments with
`isinstance(..., dict)`.

**Fix in this PR:** skip non-dict nodes. Test added.

### N2. JSDoc contracts omit fixture / live peeks the UI already reads

`ClerkCustomer` / `ClerkOrder` / `ClerkTicketRow` in
`console-src/inbox/js/contracts.js` omit `giftCards`, `discountCodes`,
`invoiceUrl`, `warranty`, `eta`, `shippingZone`, `privacySubtype`.
Inbox is JS, not TypeScript — this is doc drift, not a compiler error.

**Fix:** Optional fields on the typedefs. Comments only.

### N3. Hardcoded `"source": "sample"` on ticket handlers

`handle_list_tickets` / `get_ticket` / `escalate_ticket` always emit
`"source": "sample"` even when `HELPDESK_SOURCE=live-holes`.
`resolveLiveInbox()` keys off `source === "live"`, so this is mostly
logging/client confusion, not a GID bug.

- `console-src/helpdesk-agent/helpdesk/tissues.py`

### N4. AgentMail live pull swallows every exception

`_live_messages` `except Exception: return None` looks the same as “no
API key” and falls back to fixtures with `source: "fixture"`.

- `console-src/helpdesk-agent/helpdesk/mailbox.py`

**Fix:** Return `source: "fixture-fallback"` plus a reason. Never log the
key.

### N5. Marketing-unsubscribe scans subject only; privacy scans subject+body

Body-only “please unsubscribe me” (subject “Question”) stays
`requestType: null`. Privacy already scans both. LOCK chips then miss.

- `console-src/helpdesk-agent/helpdesk/tickets.py` (`infer_request_type`)

Bare marker `"privacy"` can also false-positive a “privacy policy”
question into the privacy gate.

### N6. MCP `tools/list` advertises refused write tools

`helpdesk.send` / `refund` / `cancel` appear in the catalog with a
`REFUSED` description. Calls fail closed. Agents may still treat them as
implemented payment paths.

- `console-src/helpdesk-agent/helpdesk/mcp_server.py`

Documented on purpose in `docs/tissues/helpdesk.md`. Keep the refusal;
consider listing them only in `write_gate_status`.

### N7. `tools/shopify_safety.py` monitors warehouse `shopify.js`, not the helpdesk client

Green warehouse scan ≠ helpdesk `client.py` / `queries.py` guarded.
Helpdesk already fail-closes via `assert_query_only`.

### N8. Doc drift

- `AGENTS.md` ticket-row `requestType` lists `marketing_unsubscribe` or
  `null` and omits `privacy_request`. `INTAKE.md` / contracts include it.
- `AGENTS.md` points at `TOKENS.md`; `helpdesk-design/` has only
  `LOCK.md` and `INTAKE.md`. Palette lives in `LOCK.md` + `styles.css`.
- Empty-rail periods: `AGENTS.md` wants `No customer.` /
  `No customer on this ticket.` `LOCK.md` has no periods. Inbox follows
  LOCK. Do not “fix” copy until LOCK and AGENTS agree.
- `composer.py` header still names retired `processor/draft_generator.py`
  / Gorgias. Wording only.

### N9. Dead or unused inbox helpers

- `FORBIDDEN_CONTROLS` export unused (`contracts.js`)
- `createOrderHistoryTissue.bind()` unused (`order-history.js`)
- `fixtureInboxCatalog()` unused (`helpdesk-shop.js`)
- Composer `SAMPLE_RAIL` numeric keys are mostly dead once
  `get_ticket()` returns canonical ids (`t-ada-track`, …)

### N10. Selected macro bar is 3px, not the 4px ink lock

`.macro-row .macro-bar` is `3px`. List rows already use the 4px
`#1C1916` ink bar. One CSS line if UX wants lock parity on macros.

### N11. Review server POST is unauthenticated

`console-src/inbox/review_server.py` `POST /console/api/helpdesk` has no
session check. Default bind is `127.0.0.1`. Not a Shopify write hole
(`WRITE_TOOLS` still refuse). Keep loopback in the VPS unit; do not bind
`0.0.0.0` without the Caddy session gate.

---

## Small fixes in this PR

Under ~50 lines. No redesign. No Admin writes.

1. `mailbox._ticket_row` keeps `requestType` (S5).
2. `line_item` omits `originalUnitPriceSet` when `shopMoney` is missing (S6).
3. `clerk_returns` skips non-dict nodes (N1).

Tests: `test_dto_lock.py`, `test_mailbox.py`.

---

## Suggested next slices (one at a time)

1. Wire `helpdesk.mark_privacy_handled` on `dispatch()` (S1). Clerk: no
   new Shopify fields.
2. Live-only join miss → GID null (S2).
3. Alias `1003` + composer `SAMPLE_RAIL` (S3).
4. Boot view vs sidebar (S4) — UX Pro vs `LOCK.md`.
5. Composer a11y names + live region + Escape on gate sheets (S9).
