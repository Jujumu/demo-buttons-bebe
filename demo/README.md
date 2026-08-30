# Cute Things demo boundary

This profile is for testing the support app against the isolated Shopify development store:

`yznyc1-ez.myshopify.com`

The latest adversarial campaign, fixes, evidence, and remaining limits are recorded in
[`TEST-REPORT.md`](TEST-REPORT.md).

It is deliberately separate from any buyer production shop. The demo profile keeps
Shopify mutations disabled, uses a separate queue database, and uses fixture-backed
localhost services for Gorgias, Redo, the knowledge base, and WhatsApp.

## Current status

The store identity has been verified through Shopify as **Cute Things** at
`yznyc1-ez.myshopify.com`. The initial snapshot contained four sample products and no orders
or customers. Do not approve a different shop in the connector.

The live demo fixtures are now seeded and tagged `AI-DEMO`:

| Order | Customer email | State | Product |
|---|---|---|---|
| `#1001` | `ai-demo-unfulfilled@example.com` | Paid, unfulfilled | Organic Cotton Baby Romper |
| `#1002` | `ai-demo-fulfilled@example.com` | Paid, fulfilled | Handcrafted Wooden Teether Toy |
| `#1003` | `ai-demo-multi@example.com` | Paid, unfulfilled | Designer Linen Baby Sun Hat |
| `#1004` | `ai-demo-multi@example.com` | Paid, fulfilled | Cashmere Knit Baby Blanket |

The fulfilled fixtures use synthetic tracking numbers `AI-DEMO-1002` and `AI-DEMO-1004`
with `example.com` tracking URLs. No receipt or customer notification was sent.

## Prepare the local profile

```bash
cp demo/.env.example demo/.env
# Fill only the separate Cute Things Shopify credentials if a read-only sync is needed.
python3 demo/verify_config.py demo/.env
```

The verifier is local-only. It requires the Cute Things demo shop, a demo-only
queue database, disabled Shopify mutations, and no static admin tokens. Keep
`demo/.env` private.

## What must be isolated

- Shopify: `yznyc1-ez.myshopify.com`, with only the read scopes needed by the
  app (`read_products`, `read_orders`, and `read_customers` where applicable).
- Gorgias: `fake_gorgias_mcp.py` provides the five read-only Hermes tools, while
  `fake_gorgias_rest.py` emulates the REST reads and captures human send/note actions
  locally with `delivered: false`.
- Redo: a separate demo store connection for return/refund scenarios, or omit those tests.
- Redo and KB emulation: this profile includes deterministic local, read-only MCP services
  in `fake_redo_mcp.py` and `fake_kb_mcp.py`. They use only the fixture files under
  `demo/fixtures/`, make no network calls, and keep return/refund scenarios synthetic.
- WhatsApp emulation: `fake_whatsapp.py` provides synthetic inbound messages and a
  localhost-only outbox compatible with `processor/whatsapp_notifier.py`. It never
  starts Baileys, pairs a phone, or delivers a WhatsApp message.
- Local state: use the demo queue database path from this profile; never reuse
  `webhook/data/webhook.db` from a production checkout.

## Run the local dependency simulators

```bash
cp demo/.env.example demo/.env
python3 demo/verify_config.py demo/.env

# Start KB, Redo, Gorgias MCP, Gorgias REST, and WhatsApp on localhost.
bash demo/run_fake_services.sh
```

To start the five simulators **and the real webhook, processor, and console**
through the fail-closed demo launcher, run:

```bash
bash demo/run_real_stack.sh
```

The launcher validates the demo profile, clears inherited Shopify/Gorgias/Redo/
WhatsApp variables, makes the shared root `.env` unavailable to demo-mode settings,
and stops the entire stack together. Use this launcher for full-system testing;
do not start the normal production service commands and assume they are a demo.

For browser testing, start `python3 demo/serve_console.py` in a second shell and
open `http://127.0.0.1:8101/`. It serves the real `console-src/index.html` and
proxies only `/console/api/*` to the localhost demo webhook on port 8100.

The service names and tool signatures remain compatible with the existing
Hermes allow-list: one KB search tool, four read-only Redo tools, and five
read-only Gorgias tools. The fake services do not write to Shopify, Redo,
Gorgias, or the production queue database.

The fake WhatsApp simulator is available at `http://127.0.0.1:8185`:

- `GET /wa/status` — connected demo identity, marked `simulated: true`
- `GET /wa/inbox` — synthetic inbound messages
- `POST /simulate/inbound` — add a synthetic inbound message
- `GET /wa/outbox` — inspect captured owner alerts
- `POST /connect-whatsapp/demo/send` — the notifier-compatible, Bearer-authenticated local sink

To exercise the processor notifier against the local sink, load only the demo
environment in that shell before running the test process:

```bash
set -a; source demo/.env; set +a
PYTHONPATH=processor python3 -c 'from whatsapp_notifier import send_whatsapp; print(send_whatsapp(1001, "Demo refund", "ai-demo@example.com", "Synthetic alert", "Demo test"))'
```

The captured message is written to `demo/data/cute-things-demo-whatsapp-outbox.jsonl`,
which is ignored local runtime state.

## Safe test sequence

1. Verify the shop identity in Shopify Admin and with the Shopify connector.
2. Read the current catalog/order/customer counts before adding anything.
3. Use only clearly prefixed demo records such as `AI DEMO - ...` and fake addresses/emails.
4. Keep `SHOPIFY_MUTATIONS_ENABLED=0` for app runtime tests. Store preparation mutations,
   if needed, are a separate, deliberate setup step in the development store.
5. Run the existing offline QA harness first; it creates no Gorgias ticket and sends no
   customer message.
6. For a full end-to-end test, send only signed synthetic webhook fixtures and confirm
   the webhook database, Gorgias base URL, result URL, WhatsApp URL, and Hermes profile
   all point to the localhost demo profile before starting the real processor.

The app's human console actions are still the only intended external write path. Shopify,
Redo, and the Hermes MCP tools remain read-only during normal processing.
