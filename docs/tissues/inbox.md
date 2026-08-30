# Inbox organ — tissue contracts

Module 9 is an **organ**: view, list, thread, composer, and rail. Rail is itself an organ of customer, this-order, returns, and order-history. Rail section titles are `h2`; nested disclosures are `h3`. Tissues are replaceable black boxes. They talk over a mailbox. They do not import each other's internals. One tissue error stays in its pane.

The shop tissue is fixture-backed in this module (`demo-inbox.example`). Clerk replaces it later with a read-only Admin GraphQL 2026-07 client. `SHOPIFY_MUTATIONS_ENABLED` stays `0`. No live store writes. The fixtures are invented demo records, not a live shop.

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

- **In:** `{ tickets, selectedTicketId, viewLabel }`
- **Out:** `{ ticketId }` on `list/selected`
- **Selected row:** 4px ink leading bar, no wash
- **Degrade:** “No tickets in this view”

### thread

- **In:** `{ ticket }`
- **Out:** `{ ticketId }` on `composer/summarize`
- Status-change lines are muted
- Skip-link copy is `Skip to thread.`
- Summarize is a stub until Caduceus is wired; it returns a summarize string to the composer contract
- **Degrade:** “Select a ticket.” Rail and composer keep their last good state

### composer

- **In:** `{ ticket, draft, summarize, macros, body }`
- **Out:** body / insert / discard / send
- To is visible. Macros live inside the box. AI draft is a strip **above** the textarea with Insert / Discard — never Send
- Send is ink fill (min-height 40px; 44px on coarse pointers) and disabled while the body is empty
- Send & close is hairline secondary, not a second ink primary. It hides on a closed ticket
- **Degrade:** “Select a ticket to reply.”

## Rail tissues

Clerk DTO field names are locked. In for each: `{ shop, customerId? , orderId? }`.

### customer

- **Out:** `displayName`, `defaultEmailAddress.emailAddress` (not deprecated `Customer.email`), `createdAt`, `numberOfOrders` (JSON string), `amountSpent`, `tags`
- Default open. Peek: name
- **Degrade:** “Customer unavailable” in this card only

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
- **Degrade:** “Returns error” in this card only
- Review block: shipping this section open while empty fails the inbox PR

### order-history

- **Out:** `{ id, name, createdAt, total, fulfillmentStatus }[]` newest first
- Default collapsed. Peek: `n orders` (e.g. `15 orders`, `1 order`, `0 orders`)
- Click peeks a row. It does not change This order
- **Degrade:** “No past orders” / card error
- Review blocks that fail the inbox PR: a fully-open rail wall (addresses + past orders + the rest), past orders open on first paint, Gorgias purple / Gaia / Ask Gaia, or a literal `null` SKU

## Shop tissue

- **In:** `{ shop, customerId?, orderId? }`
- **Out:** the Clerk DTOs above
- Fixture implementation: `console-src/inbox/js/shop/fixture-shop.js`
- Must refuse writes. Clerk swaps this tissue; the organ contract does not change
