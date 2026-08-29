# Connect your Shopify store

Buttons Bebe Support reads **your** shop from environment variables. There is
no built-in production shop. Create a Shopify app, install it on the store you
want the agent to draft for, then paste the credentials into `.env`.

Official docs:

- [Create apps using the Dev Dashboard](https://shopify.dev/docs/apps/build/dev-dashboard/create-apps-using-dev-dashboard)
- [Get API access tokens (client credentials)](https://shopify.dev/docs/apps/build/dev-dashboard/get-api-access-tokens)

Admin API version used here: **2026-07**.

## 1. Create a Dev Dashboard app

1. Open the [Dev Dashboard](https://dev.shopify.com/dashboard) and confirm you
   are in the same organization as the shop you will install on.
2. **Apps → Create app → Start from Dev Dashboard**.
3. Name the app (for example, “Support agent — read only”).

Do **not** add a `shopify.app.toml` to this repo. A Dev Dashboard app is enough.

## 2. Release a version with read scopes

On the app **Versions** tab:

1. App URL can stay `https://shopify.dev/apps/default-app-home` if the app is
   not embedded.
2. Set the Webhooks API version to **2026-07** (or the newest listed).
3. Select at least these Admin scopes (add more later if you need them):
   - `read_products`
   - `read_orders`
   - `read_customers`
   - `read_fulfillments` (optional; helps “where is my order” drafts)
4. Click **Release**.

The agent and its Shopify-backed tools stay **read-only**. Keep
`SHOPIFY_MUTATIONS_ENABLED=0` in `.env`. Human-approved Gorgias send/note
actions are the only customer-facing writes.

## 3. Install the app on your shop

1. App **Home → Install app**.
2. Choose the target shop and confirm **Install**.

The client credentials grant only works when the **app and the shop belong to
the same Shopify organization**. If token minting returns `shop_not_permitted`,
the shop is not in that org (a common cause is a store created from Shopify
admin instead of the Dev Dashboard). Create or move a store under **Dev
stores** in the same dashboard org, or distribute the app so the merchant
installs it and use a different OAuth grant.

## 4. Paste credentials into `.env`

1. Copy `.env.example` to `.env` at the repo root (never commit `.env`).
2. App **Settings**: copy **Client ID** and **Client secret**.
3. Set:

```bash
SHOPIFY_SHOP=your-store.myshopify.com
SHOPIFY_CLIENT_ID=...
SHOPIFY_CLIENT_SECRET=...
SHOPIFY_API_VERSION=2026-07
SHOPIFY_MUTATIONS_ENABLED=0
```

`SHOPIFY_SHOP` is the full `*.myshopify.com` domain, not a custom storefront
hostname.

4. Fill Gorgias and other placeholders the same way. Restart webhook,
   processor, KB sync, and the MCP tools so they reload `.env`.

Optional local sandbox: `demo/.env.example` is a **local Cute Things demo
only** (`yznyc1-ez.myshopify.com`). Do not point that profile at a live shop.

## 5. Sync the catalog (optional)

```bash
cd kb && ./sync-products.sh
```

The script mints a 24-hour Admin token with the client credentials grant, then
writes product markdown under `kb/products/`. It reads `SHOPIFY_SHOP`,
`SHOPIFY_CLIENT_ID`, and `SHOPIFY_CLIENT_SECRET` from the root `.env`.
