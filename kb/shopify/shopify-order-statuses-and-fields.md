---
title: Shopify Background — Order Statuses & Key Fields
category: shopify
status: confirmed
source: shopify-dev-docs-2026-07
tags: [shopify, orders, order-status, financial-status, fulfillment-status, tracking]
---

## What this file is

Background knowledge about how Shopify represents orders and their statuses, so
drafts interpret the order data shown on a Gorgias ticket correctly. This file
describes **Shopify platform mechanics**, not Buttons Bebe store policy — for
policy see `policies/` (shipping, returns, refunds). The agent is read-only: it
explains statuses, it never changes them.

## The three order statuses: open, closed, cancelled

Shopify groups orders into three lifecycle states. The API filter values are
`open`, `closed`, and `cancelled` (plus `not_closed` as a search shortcut).

- **Open** — normal, active state while any work remains (payment, fulfillment,
  returns).
- **Closed** — all line items are fulfilled or cancelled **and** all financial
  transactions are complete. Shopify sets `closedAt` automatically; no further
  work is expected.
- **Cancelled** — the order was cancelled (`cancelledAt` is set, and
  `cancelReason` records the reason, e.g. customer request, fraud, insufficient
  inventory). Cancellation is irreversible.

## Financial status (money state of the order)

`displayFinancialStatus` on the admin Order — how far payment/refunds have gone:

- **pending** — payment provider still processing, or manual payment method.
- **authorized** — payment details validated, charge **not yet captured**
  (manual capture stores only; capture must happen before the authorization
  expires).
- **partially_paid** — a payment was captured for less than the full total.
- **paid** — captured or marked paid.
- **partially_refunded** — some, but not all, of the payment was returned.
- **refunded** — the full amount paid was returned.
- **voided** — an authorized but uncaptured payment was voided, releasing the
  hold. Note: the **order** can remain open even when its payment is voided.
- **expired** — an authorization expired before it was captured.

## Fulfillment status (physical shipment state)

`displayFulfillmentStatus` on the admin Order:

- **unfulfilled** — nothing has shipped yet (normal during the 24–48h
  processing window; see `faq/faq-shipping-and-tracking.md`).
- **partially_fulfilled** — some items shipped, some haven't.
- **fulfilled** — everything shipped.
- **in_progress** — fulfillment request sent to a fulfillment service.
- **on_hold** — unfulfilled items are on hold.
- **scheduled** — fulfillment is scheduled for a later time.
- **request_declined** — a fulfillment service declined the request.
- **restocked** — items were returned to inventory (e.g. after a refund).

Note on vocabulary: help-desk integrations commonly show REST-style values such
as `shipped`, `unshipped`, and `partial` for the same field — treat
`shipped` as fulfilled, `unshipped` as unfulfilled.

## Key order fields useful when drafting

- **name** — the customer-facing identifier like `#1001` (admin and the
  customer's order status page both show it).
- **confirmationNumber** — a random alphanumeric customer-facing identifier
  (e.g. `XPAV284CT`); not guaranteed unique.
- **email / phone** — contact on the order; email can be null (typo) — that is
  why a customer may see a charge but no confirmation email.
- **tags / note** — merchant-added labels and instructions; note can hold gift
  messages or delivery instructions.
- **processedAt vs createdAt** — creation time never changes; processing time
  can differ from it.
- **requiresShipping** — false for digital-only orders (gift cards, downloads).
- **statusPageUrl** — the customer-facing order status page showing tracking
  and delivery updates.
- **refundable** — whether the order's payments can still be refunded.
- **merchantEditable** — whether the order can still be edited (false for
  cancelled orders and some payment statuses).

## Reading statuses on a ticket (agent workflow)

Look up the order's fulfillment status and financial status from the synced
ticket data. If unfulfilled, explain the normal processing time. If shipped,
share the tracking. If the financial status shows refunded/partially_refunded
or the order shows disputes, treat the ticket as sensitive and follow
`policies/refunds-and-disputes.md`. The agent must never promise to change any
status — a human handles those actions from the console.