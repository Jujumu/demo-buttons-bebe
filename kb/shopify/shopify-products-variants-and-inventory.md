---
title: Shopify Background — Products, Variants & Inventory
category: shopify
status: confirmed
source: shopify-dev-docs-2026-07
tags: [shopify, products, variants, inventory, sizes, catalog]
---

## What this file is

How Shopify structures the catalog (products → variants → inventory) and how
that data reaches the knowledge base, so the agent answers size/stock
questions correctly. Sizing advice itself lives in `policies/sizing-guide.md`
and the auto-synced `products/` files.

## Product vs variant

In Shopify, a **product** is the catalog entry (name, description, images,
online store page). Each purchasable combination of options (size, color,
etc.) is a **variant** with its own SKU, price, and inventory. A romper
available in S/M/L is one product with three variants — that's why "is size M
in stock" and "is this product in stock" are different questions.

## Inventory states

Inventory lives at locations (warehouses). Quantities divide into what's
**available** (sellable) and what's **committed/reserved** (held for open
orders). An item can therefore be out of stock online while reserved stock
exists for orders that haven't shipped. Shopify records whether inventory was
reserved for an order (`confirmed`) — the agent reads availability from the
synced catalog and must not promise stock it can't verify, especially during
sale season (see `policies/sale-season-and-pickup.md`).

## The synced products/ folder

The knowledge base's `products/` files are **generated automatically** from
the Shopify catalog (bulk export of active products, refreshed every 3 days,
~4,200 products). Each file has the product name, sizes/options, variant
prices, availability, description, and store link. The agent searches these
with `search_kb` for "do you have X in size Y" questions — the sync is
read-only and the agent never edits these files.

## Availability vocabulary on product files

- **active / published** — visible on the online store.
- **unavailable / sold out** — not purchasable right now (either truly out of
  stock or delisted).
- Sizes are listed per variant, so a missing size on the file means it's not
  currently offered for that product — say so, and offer the closest sizes
  or check `policies/sizing-guide.md` for fit advice.

## Agent rules for product questions

Use `search_kb` for the catalog, cite what the synced file shows, and never
guarantee future restocks (a human knows upcoming inventory, the agent
doesn't). Product questions that turn into order changes (size swap) follow
`intents/intent-08-wrong-size-switch-before-shipping.md` — and always check
whether the order already shipped first.