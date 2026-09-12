# Buttons Bebe Support

AI support-agent software for a Shopify store. Incoming helpdesk tickets get a
draft reply in the review console. A human sends, notes, edits, or discards
every draft. Shopify, Redo, and Gorgias MCP tools stay read-only except for
those human-initiated Gorgias console writes.

This repository is sellable software. **Connect your own shop** — there is no
built-in production store.

## Connect a Shopify store

See **[CONNECT.md](CONNECT.md)**. Short version:

1. Create a Dev Dashboard app and Release a version with read scopes
   (`read_products`, `read_orders`, `read_customers`; optional
   `read_fulfillments`). No write scopes.
2. Install the app on a shop in the **same Shopify organization**.
3. Copy `.env.example` to `.env` and set `SHOPIFY_SHOP`, `SHOPIFY_CLIENT_ID`,
   `SHOPIFY_CLIENT_SECRET`. Keep `SHOPIFY_MUTATIONS_ENABLED=0`. Optional:
   `AGENTMAIL_API_KEY`.
4. Run the inbox:

```bash
docker compose up --build
```

Open [http://127.0.0.1:8766/](http://127.0.0.1:8766/). Compose reads `.env`
at runtime. The image never contains secrets.

Without Docker: `./console-src/inbox/run-review.sh`.

If token minting returns `shop_not_permitted`, the app and shop are not in the
same org.

## Local Cute Things demo

`demo/.env.example` is an optional **local sandbox only**
(`yznyc1-ez.myshopify.com`). Cute Things is fixture/demo, not the default
shop. Do not point that profile at a live merchant shop. See `demo/README.md`.

## Safety model

1. The agent never sends a customer reply and never writes to Gorgias.
2. Hermes and its three MCP tools are read-only.
3. The only external writes are human-triggered console send/note actions.
4. Sensitive tickets get a prefixed draft, HIGH/CRITICAL priority, and an
   owner alert. The human remains the safety gate.

## Components

| Directory | Purpose |
|-----------|---------|
| `webhook/` | FastAPI receiver, queue, console API |
| `processor/` | Job loop, Hermes runner, draft cleaner |
| `kb/` | Knowledge base, hybrid search, product sync |
| `tools/` | Read-only Gorgias and Redo MCP modules |
| `console-src/` | Support console SPA |
| `demo/` | Isolated Cute Things sandbox |
| `testing/` | 48-scenario suite |

## Verify

```bash
bash tools/verify_release.sh
```

Never commit `.env`, filled credentials, or leftover backup trees.
