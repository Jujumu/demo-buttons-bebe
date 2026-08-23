---
title: Shopify Background — How Returns Work
category: shopify
status: confirmed
source: shopify-dev-docs-2026-07
tags: [shopify, returns, exchanges, rma, reverse-fulfillment]
---

## What this file is

How Shopify models returns and exchanges on the platform, so the agent can
interpret return data correctly. The store's **return rules** (windows, final
sale, tiers) are in `policies/return-and-exchange-policy.md` and
`policies/return-windows-and-refund-tiers.md`. For this store, return
workflows are handled through **Redo** (read via the `buttonsbebe_redo`
tools); the Shopify-side return record appears on the order as context.

## The return lifecycle

A Shopify return (`Return` object) is the intent to send one or more items
back. Its status walks through five states:

- **REQUESTED** — the customer asked to return; awaiting merchant approval.
- **OPEN** — approved and in progress (items on their way back).
- **CLOSED** — completed (refund issued, items restocked or disposed).
- **DECLINED** — the merchant refused the return request.
- **CANCELED** — the return was cancelled before any work was done.

The approval flow: a return request is created in `REQUESTED`, then a merchant
approves (→ `OPEN`) or declines it. A merchant can also create a return
directly in `OPEN` (already approved).

## What can be returned

A return can only contain **fulfilled line items that haven't been refunded
yet**. This is why a customer cannot return an item that hasn't shipped, and
why an already-refunded line item doesn't appear as returnable. Exchanges are
modeled alongside returns (exchange line items on the same return).

## The return shipment (reverse fulfillment)

An open return gets a **reverse fulfillment order** — the return shipment back
to the warehouse — with its own tracking, like a mirrored version of the
original fulfillment. That is why a return can show "in transit back to us"
before any refund is issued.

## Aggregated return status on the order

The order-level `returnStatus` summarizes all returns on the order:
`return_requested`, `in_progress`, `inspection_complete`, `returned`,
`return_failed`, or `no_return`. When a customer asks "what's happening with
my return", map that value to plain language: requested = waiting for
approval; in progress = on its way back; returned/inspection complete =
received, refund being worked.

## Return questions in this system

The agent checks return context with `buttonsbebe_redo.get_returns_for_order`
and `get_return`, and never claims a return was approved, received, or
refunded — those are human actions. Drafts cite the store's return policy and
note what the records show. Refunds attached to returns remain sensitive —
see `shopify-refunds-how-they-work.md`.