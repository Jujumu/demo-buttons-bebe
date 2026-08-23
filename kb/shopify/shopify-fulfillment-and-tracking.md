---
title: Shopify Background — Fulfillment & Tracking
category: shopify
status: confirmed
source: shopify-dev-docs-2026-07
tags: [shopify, orders, fulfillment, tracking, shipping, carriers]
---

## What this file is

How Shopify represents shipping: fulfillments, partial shipments, and tracking
information. It explains what "fulfilled", "unfulfilled", and tracking fields
mean on an order, so the agent can answer "where is my order" correctly.
Store-specific shipping times are in `faq/faq-shipping-and-tracking.md`.

## Fulfillment = the physical shipment

In Shopify, an **order** is the purchase; a **fulfillment** is a shipment. An
order's line items are grouped into fulfillment orders, and Shopify supports
sending an order in **multiple shipments** (partial fulfillment) — for example
when items come from different locations or one size ships later. The
`fulfillments` list on an order holds one record per shipment.

## What happens when an order ships

When items ship, a fulfillment is created with **tracking information**: the
tracking number, the carrier/company (USPS, UPS, ETA, etc.), and typically a
tracking URL. The customer sees the tracking number and a link on their order
status page (`statusPageUrl`) and in the shipping notification email. If the
order shows shipped but the customer says they can't find tracking, share the
number/link from the synced order data — never invent one.

## Fulfillment statuses in plain terms

- **Unfulfilled** — nothing has shipped; the order is inside the warehouse's
  processing window (24–48 hours for this store).
- **In progress** — a fulfillment request is with the fulfillment service.
- **Fulfilled** — all items shipped.
- **Partial / partially fulfilled** — some items shipped, others still pending;
  explain which items are on the way and which are still preparing.
- **On hold** — items deliberately held (e.g. fraud check or address issue).
- **Scheduled** — fulfillment will run later (e.g. pre-orders).
- **Request declined** — a fulfillment service refused the request.
- **Restocked** — items returned to inventory rather than shipped (cancelled or
  returned items).

## Fulfillable and non-fulfillable line items

An order has a `fulfillable` flag and a list of non-fulfillable line items
(e.g. tips, or fully refunded line items). This explains why a partially
refunded order may ship only part of its contents: refunded items stop being
fulfillable. The agent should read this as context, never as something to
change.

## Tracking rules for drafting

- Only share tracking when the synced order data shows the item shipped.
- Processing time and carrier time are separate: explain both (see
  `faq/faq-shipping-and-tracking.md`).
- Never promise a carrier's delivery date; recommend faster shipping only
  before fulfillment.
- If tracking shows delivered but the customer says the package is missing,
  that is a sensitive lost-package case — follow
  `policies/lost-or-stolen-package.md`.

## Agent boundary (read inside each chunk)

The agent must not claim it shipped, held, or re-routed anything. Any request
to change fulfillment goes to a human via a staff handoff draft; the agent only
reports the status Shopify already has.