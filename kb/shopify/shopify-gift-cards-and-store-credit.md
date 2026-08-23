---
title: Shopify Background — Gift Cards & Store Credit
category: shopify
status: confirmed
source: shopify-dev-docs-2026-07
tags: [shopify, gift-cards, store-credit, balance, checkout]
---

## What this file is

How Shopify gift cards and store credit work on the platform, so the agent can
answer balance and redemption questions accurately. Store-specific gift
policies (gift wrapping, notes, final sale) are in
`policies/gifts-and-gift-wrapping.md`; when the store offers store credit
instead of a refund is policy in `policies/refund-windows-and-refund-tiers.md`.

## Gift card basics

A Shopify gift card has a **code**, an **initial value**, and a **current
balance**. It may have an expiry date (`expiresOn`) and is either **enabled**
or disabled. Deactivation is **irreversible** — a deactivated gift card cannot
be used again or re-enabled, so only a human decides to deactivate one (e.g.
for fraud), never the agent.

## Purchased vs manually issued gift cards

- **Purchased** — bought through checkout like a product; the gift card is
  linked to the order that created it and can be sent to a recipient with a
  personalized message. Digital-only: a gift card order has no shipping
  (`requiresShipping: false`), which explains why it has no tracking.
- **Manual / store-issued** — created by the merchant (for example when store
  credit is given). These have no associated order.

## Using a gift card at checkout

A customer enters the gift card code at checkout and it pays all or part of
the order. Balances survive partial use — the remainder stays on the card for
future orders. Gift cards can be combined with other payment methods. Gift
card status values in the admin include `enabled`, `disabled`, `expired`,
`expiring`; balance states are `full`, `partial`, `empty`.

## Store credit from refunds and cancellations

When an order is cancelled (or refunded) to store credit, Shopify issues a
store-credit balance — which may carry an **expiration date** set at issue
time. That is why a cancellation confirmation can say "store credit expiring
on <date>". If a customer asks what happened to their store credit, the agent
reports what the records show and never invents a balance.

## Answering gift card questions

- "Where is my gift card?" — purchased gift cards are delivered by email to
  the buyer or recipient; check the order data for the recipient attributes
  before drafting, and note resending is a human action.
- "What's my balance?" — the agent cannot look up a card by code itself; draft
  a handoff so a human checks the admin.
- The agent must not claim it created, deactivated, or re-sent a gift card —
  those are human console actions only.