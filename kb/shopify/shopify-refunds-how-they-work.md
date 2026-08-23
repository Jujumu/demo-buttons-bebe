---
title: Shopify Background — How Refunds Work
category: shopify
status: confirmed
source: shopify-dev-docs-2026-07
tags: [shopify, refund, money, transactions, restocking, store-credit]
---

## What this file is

How Shopify represents refunds on the platform: what a refund is made of, how
it flows, and what the order data tells you. **Store refund policy (windows,
restocking fees, tiers) lives in `policies/refunds-and-disputes.md` and
`policies/return-windows-and-refund-tiers.md` — those files always govern what
the agent drafts.** This file only explains the Shopify mechanics behind them.

## What a refund record contains

A Shopify refund is a financial record attached to an order. It is composed of
refund **line items** (which items, quantities, amounts), refunded **shipping**
lines, taxes, and duties, with optional **restocking** (returning the items to
inventory). Refunds can be **full or partial** — a partial refund covers some
line items, or only shipping, and leaves the rest of the order paid.

## A refund record does not mean money has arrived

Important nuance: the refund record being created doesn't guarantee the money
has reached the customer. The actual movement happens through **order
transactions**, which have their own states — pending, processing, success, or
failure. When a customer asks "where is my refund", the accurate answer
depends on the transaction status, not just the existence of the refund. If
the data doesn't show a successful transaction, the reply must say it's
processing — never promise a landed amount without the transaction state.

## How the order's financial status reflects refunds

- **partially_refunded** — some but not all of the payment returned.
- **refunded** — the full amount paid was returned.
- `netPaymentSet` — amount received minus amount refunded.
- The order's `refundable` flag shows whether further refunds are still
  possible; a fully refunded order is not refundable.

## Refund destinations and store credit

A refund can go back to the **original payment method** (card, etc.) or be
issued as **store credit / gift card balance**. When an order is cancelled and
refunded to store credit, Shopify creates store credit with an expiration
date. See `shopify-gift-cards-and-store-credit.md` for how that balance works
and `policies/refund-windows-and-refund-tiers.md` for when the store offers
store credit instead of a refund.

## Restocking

Refunding items can optionally **restock** them into inventory so the size can
be sold again. Restocking is a human action in the admin; the agent never
performs it and must not promise a restock happened. Whether a restocking fee
applies is store policy — see `policies/restocking-fees.md`.

## Refund requests in this system (sensitive)

Any ticket about a refund is **sensitive**: draft with the
`[SENSITIVE — REVIEW CAREFULLY BEFORE SENDING]` prefix, elevate for human
review, and never send it yourself. The agent is read-only — it must not
claim it issued or processed a refund; it drafts an acknowledgment and the
human acts. See `policies/refunds-and-disputes.md` and
`policies/sensitive-draft-policy.md`.