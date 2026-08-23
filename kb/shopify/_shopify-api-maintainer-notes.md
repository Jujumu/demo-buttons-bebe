---
title: Shopify API — Maintainer Notes (NOT indexed)
category: shopify
status: confirmed
source: shopify-dev-docs-2026-07
tags: [shopify, api, auth, rate-limits, bulk-operations, maintainers]
---

> This file starts with `_` so the KB indexer skips it. It is developer
> reference for maintaining this system — not agent-facing content. Hermes
> must still never call Shopify directly (see `hermes/skills/buttonsbebe/shopify/SKILL.md`).

## Auth in this system (client credentials grant)

This repo uses a Shopify **custom app** with a client-credentials grant:

```http
POST https://{shop}.myshopify.com/admin/oauth/access_token
Content-Type: application/x-www-form-urlencoded

client_id=<SHOPIFY_CLIENT_ID>
client_secret=<SHOPIFY_CLIENT_SECRET>
grant_type=client_credentials
```

- Token lifetime: **24 hours** (`expires_in` is `86399`). Refresh = repeat the
  same request.
- GraphQL Admin requests send it as `X-Shopify-Access-Token: <token>`.
- Credentials live in the root `.env` (`SHOPIFY_SHOP`, `SHOPIFY_CLIENT_ID`,
  `SHOPIFY_CLIENT_SECRET`) — never commit `.env*` or
  `_VPS-FULL-BACKUP-*/`.
- Used today by `kb/scripts/sync_products.py` (scope `read_products`) to mint
  a fresh 24h token and run a **bulk products export**. Order data reaches the
  agent through Gorgias' synced Shopify data — there is no direct
  Shopify orders API call in the live pipeline.

## Rate limits that matter

- GraphQL Admin API uses **calculated query cost**, not request counts:
  100 points/second (standard plan), 200 (Advanced), 1000 (Plus). Leaky-bucket
  model with burst capacity.
- A **single query may not exceed 1,000 cost points**, enforced before
  execution.
- Input arrays are capped at **250 elements**; pagination is capped at
  **25,000 objects** (counts return 25,001 as "more than").
- **Bulk operations** (what `sync_products.py` uses) are exempt from the
  per-query cost and rate limits — designed for large exports like a ~4,200
  product catalog.
- Throttled requests should back off (~1s) and retry; treat throttling as
  expected behavior on shared limits.

## REST vs GraphQL, versions, deprecations

- GraphQL Admin is the primary API today; REST Admin still exists
  (`/admin/api/<version>/...`). Several GraphQL fields are marked deprecated
  (`totalRefunded`, `netPayment`, `riskLevel`…) — new code should use the
  `*Set` money fields.
- APIs are **versioned** (e.g. `2026-07`); `latest` resolves to the newest
  stable version. Pin versions when stability matters; deprecated fields
  survive until the API version is sunset.
- Some mutations now **require idempotency keys** (e.g. `refundCreate` since
  2026-04) — note if this system ever gains write paths (it must not without
  revisiting the safety model).

## What the agent must NOT do (unchanged safety model)

The knowledge files in this folder describe platform concepts only. The live
pipeline's safety rules are unchanged: Hermes never calls Shopify directly,
never loads credentials, never writes Gorgias or Shopify — it returns drafts
to the review console. See AGENTS.md §2 and the `shopify` Hermes skill.

## Source references (fetched 2026-08 for this folder)

- https://shopify.dev/docs/api/admin-graphql/latest/objects/Order
- https://shopify.dev/docs/api/admin-graphql/latest/enums/OrderDisplayFinancialStatus
- https://shopify.dev/docs/api/admin-graphql/latest/enums/OrderDisplayFulfillmentStatus
- https://shopify.dev/docs/api/admin-graphql/latest/objects/Refund
- https://shopify.dev/docs/api/admin-graphql/latest/objects/Return
- https://shopify.dev/docs/api/admin-graphql/latest/enums/ReturnStatus
- https://shopify.dev/docs/api/admin-graphql/latest/enums/DisputeStatus
- https://shopify.dev/docs/api/admin-graphql/latest/mutations/orderCancel
- https://shopify.dev/docs/api/admin-graphql/latest/objects/GiftCard
- https://shopify.dev/docs/apps/build/authentication-authorization/access-tokens
- https://shopify.dev/docs/api/usage/limits
- https://help.shopify.com/en/manual/fulfillment/managing-orders/editing-orders/considerations