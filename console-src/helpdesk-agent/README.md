# Helpdesk agent organ

MCP server + CLI for the Shopify helpdesk. UI is a client, not the product.
Each of the ten v1 tools is a tissue: one handler, two doors (MCP and CLI).

```text
helpdesk list-tickets --view open --limit 20
helpdesk get-ticket --ticket-id 1001
helpdesk get-customer --shop demo-helpdesk.example \
  --customer-id gid://shopify/Customer/9001
helpdesk get-order --shop yznyc1-ez.myshopify.com \
  --order-id gid://shopify/Order/7131035795629
helpdesk draft-reply --ticket 1001
helpdesk summarize-thread --ticket 1001
helpdesk search-macros --query shipping
helpdesk apply-macro --macro-id shipping-delay --mode replace
helpdesk serve          # MCP stdio
helpdesk tools          # list the ten tool names
```

JSON on stdout. Failures are structured JSON (no stack traces).

The inbox is a client of the same ten tools. The console HTTP door is
`POST /console/api/helpdesk` (`{ tool, arguments }`) and calls `invoke()`.
Mint/Admin failure falls back to the inbox fixture shop. `SHOPIFY_MUTATIONS_ENABLED`
stays `0`. Env names (values live only in `.env`): `SHOPIFY_SHOP`,
`SHOPIFY_CLIENT_ID`, `SHOPIFY_CLIENT_SECRET`.

From this directory:

```bash
PYTHONPATH=. python3 -m helpdesk tools
PYTHONPATH=. python3 -m helpdesk serve
PYTHONPATH=. python3 -m unittest discover -s tests -v
```

Shop reads use env (`SHOPIFY_SHOP`, `SHOPIFY_CLIENT_ID`, `SHOPIFY_CLIENT_SECRET`).
Live mint is pinned to `yznyc1-ez.myshopify.com` from `SHOPIFY_SHOP` only and
does not follow token-URL redirects. If minting fails, handlers fall back to
sample fixtures. `SHOPIFY_MUTATIONS_ENABLED` stays `0`.

Tissue contracts: [`docs/tissues/helpdesk.md`](../../docs/tissues/helpdesk.md).
