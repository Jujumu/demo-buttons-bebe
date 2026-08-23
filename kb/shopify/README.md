---
title: Shopify Background Folder — README
category: shopify
status: confirmed
source: shopify-dev-docs-2026-07
tags: [shopify, background, reference]
---

## What this folder is

Reference knowledge about **how the Shopify platform works** — order
statuses, fulfillment, refunds, returns, cancellations, payments, gift cards,
and the catalog model — researched from the official Shopify developer
documentation (shopify.dev, API version 2026-07) and the Shopify Help Center
in 2026-08.

It complements the store-policy folders: `policies/` holds Buttons Bebe's
rules and reply posture; `shopify/` holds the platform mechanics those rules
operate on. When a ticket needs a factual platform explanation (what
"partially refunded" means, why a pending charge disappears on cancellation),
the agent grounds that part of the draft here; the store's policy files still
govern what the reply promises.

## Files (all indexed unless `_`-prefixed)

| File | Covers |
|---|---|
| `shopify-order-statuses-and-fields.md` | order/financial/fulfillment statuses, key fields |
| `shopify-fulfillment-and-tracking.md` | shipments, partial fulfillment, tracking |
| `shopify-refunds-how-they-work.md` | refund mechanics, transactions, store credit |
| `shopify-returns-how-they-work.md` | return lifecycle, approvals, reverse fulfillment |
| `shopify-cancellations-and-order-editing.md` | cancel rules, order/address editing limits |
| `shopify-payments-authorization-and-disputes.md` | auth vs capture, disputes/chargebacks |
| `shopify-gift-cards-and-store-credit.md` | gift card model, store credit |
| `shopify-products-variants-and-inventory.md` | catalog model, the synced products/ corpus |
| `_shopify-api-maintainer-notes.md` | API auth/limits reference — **not indexed**, for maintainers |

## Conventions

- Frontmatter declares `category: shopify` so chunks are labeled correctly in
  search results.
- Sensitive-topic files (refunds, cancellations/address, payments/disputes)
  carry their topic tags, so the existing sensitivity taxonomy marks them the
  same way the corresponding policy files are marked.
- Each `##` section is self-contained: the read-only boundary and the
  "human performs the action" guard appear inside the same chunk, matching
  the KB's operational-language test.
- `source: shopify-dev-docs-2026-07` records provenance. After adding or
  editing content, run `./update.sh` so the index picks it up.

## Not in scope

Store policy, reply macros, and escalation rules stay in `policies/`,
`intents/`, and `faq/`. This folder must never duplicate a store promise; if a
platform fact and a store policy ever conflict, the store policy wins in
drafts.