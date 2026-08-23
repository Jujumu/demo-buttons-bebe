---
title: Shopify Background — Cancellations & Order Editing
category: shopify
status: confirmed
source: shopify-dev-docs-2026-07
tags: [shopify, orders, cancel, address-change, order-editing, size-swap]
---

## What this file is

What Shopify allows (and forbids) when cancelling or editing an order, so the
agent never promises an impossible change and drafts accurate handoffs. Store
policy for cancellation requests is in
`policies/order-changes-and-cancellations.md`. The agent is read-only — it
never cancels or edits an order itself.

## Cancellation rules (Shopify side)

An order can only be cancelled when ALL of these hold:

- it hasn't already been cancelled;
- it has **no pending payment authorizations**;
- it has **no active returns in progress**;
- it has **no outstanding fulfillments that can't be cancelled**.

Cancellation is **irreversible** — a cancelled order can't be restored to its
original state. When an order is cancelled, Shopify can simultaneously:
refund to the original payment method **or** create store credit (with an
expiration), restock the inventory, and notify the customer by email. A
staff-facing note can be attached — it is never shown to the customer.
These are Shopify-side mechanics the agent only describes — a human performs
the actual cancellation, and the agent must not claim it happened.

## Authorized payments on cancellation

If the payment was only **authorized** (a temporary hold, not yet captured),
cancelling the order **automatically releases the hold** — the charge voids
and the customer is not actually charged, even if no refund is chosen. This is
why a customer who cancels quickly sees the pending charge simply disappear
instead of a refund appearing.

## What can be edited on an open order

Shopify's order editing allows, before fulfillment:

- add or remove **unfulfilled** products, and adjust their quantities;
- update **shipping fees** (add a custom shipping charge);
- add, change, or remove **manual line-item discounts**.

What cannot be edited:

- **fulfilled** items (cannot remove them or change their quantity);
- order-level discounts, **discount codes**, script discounts, and automatic
  discounts;
- the **delivery method** (can't switch shipping ↔ pickup);
- orders paid with Shop Pay Installments (refund + new order instead);
- orders with pending payment (limited); imported/app-created orders;
- local-delivery orders.

## Shipping address changes

A shipping address can be changed during order editing **before fulfillment**;
when the address changes, Shopify recalculates taxes for the new destination
(and the customer may owe or be owed the difference). Once items have shipped,
the address can't be changed on the order. That is why address corrections
must happen fast and why a shipped order needs a different path — always
check the fulfillment status first (see
`intents/intent-10-zip-code-address-correction.md`).

## Cancellation is asynchronous

Shopify runs cancellations as a background job — the request is accepted and
the cancellation completes moments later. In drafts, never claim a
cancellation finished; say a request has been passed to the team and the
agent/human will confirm. Cancellation and address-change tickets are
sensitive: draft with the sensitive prefix and elevate for human review.

## Agent boundary (read inside each chunk)

The agent must not claim it cancelled, edited, or changed an address. It
checks the order's status, drafts a precise staff handoff with the requested
change, and notes whether the order is still editable (unfulfilled) — the
human performs the action from the console.