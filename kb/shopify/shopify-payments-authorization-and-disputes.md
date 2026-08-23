---
title: Shopify Background — Payments, Authorizations & Disputes
category: shopify
status: confirmed
source: shopify-dev-docs-2026-07
tags: [shopify, payments, authorization, transactions, chargeback, dispute]
---

## What this file is

How payments flow on Shopify — authorization vs capture, why customers see
pending charges, and how chargebacks/disputes appear on an order — so the
agent explains money questions accurately. Disputes are **always sensitive**;
reply rules are in `policies/refunds-and-disputes.md`.

## Authorization vs capture

Most payments have two steps. **Authorization** validates the card and
reserves the amount (the customer sees a *pending* charge). **Capture** moves
the money. Most stores capture automatically when the order is processed;
stores using manual capture must capture before the authorization expires.

- **authorized** financial status — card validated, not yet captured.
- **expired** — the authorization lapsed before capture; no charge completes.
- **voided** — the hold was released; the order itself can remain open.
- **pending** — the provider needs more time, or a manual payment method is
  in use.

## Order transactions

Money movements on an order are recorded as transactions with their own
states: pending, processing, success, or failure. A refund record or a charge
on the order only means money moved when its transaction reached success —
until then the honest answer is "processing". The agent must not claim a
payment or refund completed when the synced data only shows pending.

## Disputes and chargebacks

A **dispute** is when a customer challenges a charge with their bank or card
issuer. On the order this appears as a dispute summary with a status:

- **NEEDS_RESPONSE** — the merchant must submit evidence by the deadline
  (this is the urgent one to flag for the owner).
- **UNDER_REVIEW** — evidence submitted, the bank is deciding.
- **WON** — the merchant kept the funds.
- **LOST** — the bank sided with the customer; funds reversed.
- **ACCEPTED** — the merchant accepted liability.
- **PREVENTED** — the dispute never became a formal chargeback.

Disputes can be initiated as chargebacks or as payment inquiries
(less formal questions from the issuer). Some orders are covered by
**Shopify Protect**, which reimburses the merchant for fraudulent chargebacks
on eligible orders.

## Why a customer's question needs escalation

Any ticket mentioning a chargeback, dispute, or "bank reversed my charge"
is sensitive. The agent drafts with the
`[SENSITIVE — REVIEW CAREFULLY BEFORE SENDING]` prefix, never sends it itself,
and flags the needs-response deadline if the data shows one. Chargeback
replies are grounded in `policies/refunds-and-disputes.md` — the human is the
only one who may promise outcomes.

## Agent boundary (read inside each chunk)

The agent must not claim it captured a payment, voided a charge, submitted
evidence, or won a dispute. It reports what the order data shows and drafts a
handoff for a human to act.