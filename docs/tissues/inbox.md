# Inbox organ — tissue contracts

Module 9 is an **organ**: view, list, thread, composer, and rail. Rail is itself an organ of customer, this-order, returns, and order-history. Rail section titles are `h2`; nested disclosures are `h3`. Tissues are replaceable black boxes. They talk over a mailbox. They do not import each other's internals. One tissue error stays in its pane.

The shop tissue is a client of `helpdesk.get_customer` / `get_order` /
`get_returns` / `list_past_orders` (same payloads as MCP/CLI). Views, list,
and thread are clients of `helpdesk.list_tickets` (`{ view, limit }`) and
`helpdesk.get_ticket` (`{ ticketId }`) on that same `invoke()` path. List
rows carry `customerId` / `orderId` GIDs so the rail lights when a ticket is
selected. Composer Insert/Discard and the mute summarize peek are clients of
`helpdesk.draft_reply` and `helpdesk.summarize_thread`. In-box macro search is
a client of `helpdesk.search_macros`; Insert/Append call `helpdesk.apply_macro`
(`replace` or `append`) and never send. Email/chat intake is a client of
`helpdesk.ingest_email` / `helpdesk.ingest_chat` on that same path. Live reads target Cute Things
(`SHOPIFY_SHOP` pinned to `yznyc1-ez.myshopify.com`) when mint works.
Mint/Admin failure falls back to `demo-inbox.example` fixtures.
`SHOPIFY_MUTATIONS_ENABLED` stays `0`. No live store writes. The Ada OPEN
return is invented fixture-only and is never injected onto a live shop query.
No `helpdesk.send`.

Demo names only (Ada Demo, Casey Sandbox, Jordan Preview). No customer PII.

## Mailbox topics

| Topic | Payload | Who publishes |
|---|---|---|
| `view/selected` | `{ viewId }` | view |
| `list/selected` | `{ ticketId }` | list |
| `composer/body` | `{ text }` | composer |
| `composer/insert` | `{ text }` | composer (macro or AI Insert) |
| `composer/discard` | `{}` | composer (AI Discard) |
| `composer/send` | `{ text, close }` | composer Send / Send & close — never the AI strip |
| `composer/summarize` | `{ ticketId }` | thread |
| `history/peek` | `{ orderId }` | order-history — does **not** replace This order |
| `tissue/error` | `{ tissueId, message }` | any tissue that fails closed |

## Inbox tissues

### view

- **In:** `{ views, counts, selectedViewId }`
- **Out:** `{ viewId }` on `view/selected`
- **Default views:** Assigned to me, Unassigned, All, Snoozed, Closed
- **Degrade:** empty list; other panes stay

### list

- **In:** `{ tickets, selectedTicketId, viewLabel }` from `helpdesk.list_tickets`
- **Out:** `{ ticketId }` on `list/selected`
- Row copy uses first-party `customerName` and `snippet` (never `displayName`)
- **Selected row:** One leading-edge ink bar on the selected ticket (4px). That is the only selection treatment. No wash, no purple. Surface only (`#FFFDF9`); bar is `#1C1916`.
- **Degrade:** “No tickets in this view”

### thread

- **In:** `{ ticket }` from `helpdesk.get_ticket` (`ticket` + `messages` + `statusEvents`)
- **Out:** `{ ticketId }` on `composer/summarize`
- Status-change events are muted as `Closed · Tuesday` (ticket status + weekday). That is a status event, not `Order.displayFulfillmentStatus`. The Ada fixture includes at least one status event so the mute line is visible.
- The ticket badge is title case (`Open`), not `OPEN`. Ticket status is `open` / `closed` / `snoozed`, never `Return.status`.
- Skip-link copy is `Skip to thread.`
- Summarize publishes `composer/summarize`. Caduceus fills a mute peek via `helpdesk.summarize_thread`. It does not Send and does not open an AI sidebar.
- **Degrade:** “Select a ticket.” Rail and composer keep their last good state

### composer

- **In:** `{ ticket, draft, summarize, macros, body }`
- **Out:** body / insert / discard / send
- To is visible. Macro search lives **inside** the composer box (not a floating panel over the thread). Pick a row, then Replace or Append. Those fill the textarea via `helpdesk.apply_macro` and never Send. Replace (not Insert) is the macro verb so it does not collide with the signed draft-strip Insert. After Replace/Append the picker closes.
- AI draft is a strip **above** the textarea with Insert / Discard — never Send. The AI draft kicker is mute (accent is unread/error only). Draft text comes from `helpdesk.draft_reply`.
- Summarize is a mute peek **above** the composer box, never a send. It does not enable Send by itself.
- Send is ink fill (min-height 40px; 44px on coarse pointers) and disabled while the body is empty
- Send & close is hairline secondary, not a second ink primary. It hides on a closed ticket
- **Degrade:** “Select a ticket to reply.”

## Rail tissues

Clerk DTO field names are locked. In for each: `{ shop, customerId? , orderId? }`.

### customer

- **Out:** `displayName`, `defaultEmailAddress.emailAddress` (not deprecated `Customer.email`), `createdAt`, `numberOfOrders` (JSON string), `amountSpent`, `tags`
- Default open. Peek: name
- No Customer Edit link. No `customerUpdate` / address writes.
- **Degrade:** “No customer on this ticket” in this card only

### order (This order)

- **Out:** `name`, `createdAt`, `displayFinancialStatus`, `displayFulfillmentStatus`, `currentTotalPriceSet` (MoneyBag `{ shopMoney, presentmentMoney }`), `lineItems` (`title`, `sku`, `qty`, `originalUnitPriceSet.shopMoney`), stacked `shippingAddress` / `billingAddress`, `fulfillments.trackingInfo`, plus totals when the order object has them
- Default open. Peek: order number + Paid + Fulfilled
- Line items and totals stay visible while open
- Addresses start collapsed (stack, not two columns). Peek `No billing` when `billingAddress` is missing. `Ship ≠ bill` / `Same address` only when both addresses exist
- Shipment opens only when tracking exists. Tracking is a labeled link, not a URL dump
- Null or empty SKU omits the mono SKU row entirely. Do not print `null`. Do not print an em dash that occupies a SKU column. Do not invent a SKU
- Clicking a past order does **not** replace this section
- **Degrade:** “No order on this ticket”

### returns

- **Out:** `returns.nodes[].status` (Return.status). In-progress is `Return.status === "OPEN"` only. Do not read `Order.returnStatus`. There is no `PENDING` ReturnStatus.
- Ada #1001 has one invented OPEN return so default-open can be reviewed on first paint. Peek is lock-style: `In transit · 1 item` (status word + item count when there is no tracking). This OPEN fixture is the only default-open case; other invented tickets stay empty.
- User toggle wins: clicking Returns closed stays closed. Expand state resets to lock defaults when `ticketId` / `orderId` changes (Customer + This order open; Returns open only if THIS ticket has an OPEN return; Past orders and Addresses collapsed).
- Empty tickets (Casey / Jordan / no-order) stay collapsed with peek `No returns`
- **Degrade:** “Couldn't load Returns. Retry.” in this card only
- On-screen status word is title case (`Open`). The data enum stays `OPEN`.
- No Edit / Duplicate / Refund / Cancel / Create order controls. v1 is read-only.
- Review block: shipping this section open while empty fails the inbox PR

### order-history

- **Out:** Clerk `list_past_orders` rows (`id`, `name`, `createdAt`, `displayFulfillmentStatus`, `currentTotalPriceSet.shopMoney`) newest first. The view layer projects `total` + `fulfillmentStatus` for render.
- Default collapsed. Peek: `n orders` (e.g. `15 orders`, `1 order`, `0 orders`)
- Click peeks a row. It does not change This order
- **Degrade:** “No past orders” / card error
- Review blocks that fail the inbox PR: a fully-open rail wall (addresses + past orders + the rest), past orders open on first paint, Gorgias purple / Gaia / Ask Gaia, or a literal `null` SKU

## Shop tissue

- **In:** `{ shop, customerId?, orderId? }`
- **Out:** the Clerk DTOs above (same as helpdesk MCP/CLI)
- Client: `console-src/inbox/js/shop/helpdesk-shop.js` via
  `POST /console/api/helpdesk` → `helpdesk.invoke()`
- Views / list / thread use the same client for `helpdesk.list_tickets` and
  `helpdesk.get_ticket`. Composer uses it for `helpdesk.draft_reply`,
  `helpdesk.summarize_thread`, `helpdesk.search_macros`, and
  `helpdesk.apply_macro`. Draft-strip Insert/Discard and macro Replace/Append never call send.
- Fallback: `console-src/inbox/js/shop/fixture-shop.js` when mint/Admin/HTTP
  is unavailable, or when the requested GID is only on the fixture catalog
- Live Cute Things (`source=live`) remounts the inbox onto live GIDs. Empty
  live returns stay empty. Ada OPEN stays fixture-only.
- Must refuse writes. `SHOPIFY_MUTATIONS_ENABLED` stays `0`.
- Error copy, isolated per pane: `Couldn't load [Customer/Order/Returns/History]. Retry.`
