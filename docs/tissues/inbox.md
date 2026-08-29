# Inbox organ — tissue contracts

Module 9 is an **organ**: view, list, thread, composer, and rail. Rail is itself an organ of customer, this-order, returns, and order-history. Tissues are replaceable black boxes. They talk over a mailbox. They do not import each other's internals. One tissue error stays in its pane.

The shop tissue is fixture-backed in this module. Clerk replaces it later with a read-only Admin GraphQL 2026-07 client. `SHOPIFY_MUTATIONS_ENABLED` stays `0`. No live store writes.

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
- Summarize is a stub until Caduceus is wired; it returns a summarize string to the composer contract
- **Degrade:** “Select a ticket.” Rail and composer keep their last good state

### composer

- **In:** `{ ticket, draft, summarize, macros, body }`
- **Out:** body / insert / discard / send
- To is visible. Macros live inside the box. AI draft is a strip with Insert / Discard — never Send
- Send is ink and disabled while the body is empty. Send & close hides on a closed ticket
- **Degrade:** “Select a ticket to reply.”

## Rail tissues

Clerk DTO field names are locked. In for each: `{ shop, customerId? , orderId? }`.

### customer

- **Out:** `displayName`, `defaultEmailAddress.emailAddress` (not deprecated `Customer.email`), `createdAt`, `numberOfOrders`, `amountSpent`, `tags`
- Default open. Peek: name
- **Degrade:** “Customer unavailable” in this card only

### order (This order)

- **Out:** `name`, `createdAt`, `displayFinancialStatus`, `displayFulfillmentStatus`, `currentTotalPriceSet`, `lineItems` (`title`, `sku`, `qty`, `price`), stacked `shippingAddress` / `billingAddress`, `fulfillments.trackingInfo`, plus totals when the order object has them
- Default open. Peek: order number + Paid + Fulfilled
- Line items and totals stay visible while open
- Addresses start collapsed (stack, not two columns). Peek `Ship ≠ bill` when billing is missing or different
- Shipment opens only when tracking exists. Tracking is a labeled link, not a URL dump
- Null SKU renders as an em dash. Do not invent a SKU
- Clicking a past order does **not** replace this section
- **Degrade:** “No order on this ticket”

### returns

- **Out:** `returns`, `returnStatus`, in-progress flag, items + reason/type, refund vs credit totals, return tracking
- Cute Things fixtures are empty: peek `No returns`, collapsed
- Open only when a return is in progress. Empty Cute Things fixtures stay collapsed with peek `No returns`
- **Degrade:** “Returns error” in this card only
- Review block: shipping this section open while empty fails the inbox PR

### order-history

- **Out:** `{ id, name, createdAt, total, fulfillmentStatus }[]` newest first
- Default collapsed. Peek: count
- Click peeks a row. It does not change This order
- **Degrade:** “No past orders” / card error
- Review blocks that fail the inbox PR: a fully-open rail wall (addresses + past orders + the rest), past orders open on first paint, Gorgias purple / Gaia / Ask Gaia, or a literal `null` SKU

## Shop tissue

- **In:** `{ shop, customerId?, orderId? }`
- **Out:** the Clerk DTOs above
- Fixture implementation: `console-src/inbox/js/shop/fixture-shop.js`
- Must refuse writes. Clerk swaps this tissue; the organ contract does not change
