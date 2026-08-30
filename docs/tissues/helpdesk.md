# Helpdesk organ — tissue contracts

Agent-native organ. The UI is a client. Every tissue is a black box
(`In → Out`) exposed as an MCP tool and a CLI command on the **same handler**.

This organ does **not** wrap Gorgias. Ticket tissues are first-party.
Shopify rail tissues speak Admin GraphQL **2026-07** field names only.

## Tools (v1, ten)

Six rail/inbox reads, two Caduceus composer tools, and two macro tools.
Composer and macro tools return text. They never send, refund, or cancel.

| Tool | Tissue | CLI | In | Out |
|---|---|---|---|---|
| `helpdesk.list_tickets` | list | `helpdesk list-tickets` | `{ view, limit }` | ticket rows |
| `helpdesk.get_ticket` | thread | `helpdesk get-ticket` | `{ ticketId }` | ticket + messages + status events |
| `helpdesk.get_customer` | customer | `helpdesk get-customer` | `{ shop, customerId }` GID | `ClerkCustomer` |
| `helpdesk.get_order` | order | `helpdesk get-order` | `{ shop, orderId }` GID | `ClerkOrder` |
| `helpdesk.get_returns` | returns | `helpdesk get-returns` | `{ shop, orderId }` GID | returns payload |
| `helpdesk.list_past_orders` | order-history | `helpdesk list-past-orders` | `{ shop, customerId }` GID | `ClerkOrderHistoryRow[]` newest first |
| `helpdesk.draft_reply` | composer draft | `helpdesk draft-reply --ticket …` | `{ ticketId, shop?, thread?, rail DTOs? }` | `{ draft }` for Insert/Discard |
| `helpdesk.summarize_thread` | composer peek | `helpdesk summarize-thread --ticket …` | `{ ticketId, thread? }` | `{ summary }` mute peek, never a send |
| `helpdesk.search_macros` | composer macros | `helpdesk search-macros --query …` | `{ query? }` | `{ macros: [{ id, title, body, tags }] }` |
| `helpdesk.apply_macro` | composer insert | `helpdesk apply-macro --macro-id … --mode replace\|append` | `{ macroId, mode?, currentBody? }` | `{ text, title, mode, body }` for the textarea |

**Macro contract.** `search_macros` always returns the fixture body so a client
can insert without a second call. `apply_macro` is the insert path: `replace`
overwrites the box, `append` adds after existing text. Neither tool sends.
The human still hits Send. Fixtures (offline): Shipping delay, Return how-to,
Order status.

No `helpdesk.send`, `helpdesk.refund`, or `helpdesk.cancel`. Those stay in
`WRITE_TOOLS` and are refused. `SHOPIFY_MUTATIONS_ENABLED` stays `0`.

The inbox is a client of these ten tools. MCP, CLI, and
`POST /console/api/helpdesk` (`{ tool, arguments }`) share `invoke()`.
The UI must not open a second GraphQL client.

Rail IDs are Shopify GIDs (`gid://shopify/Customer/…`, `gid://shopify/Order/…`),
not bare ticket numbers. Ticket tissues keep `view` / `limit` / `ticketId`.
Composer `--ticket` is the ticket id (sample `1001` or an already-loaded inbox thread).

Drafts are merchant replies the human Inserts or Discards. Summaries are a
short mute peek of the thread, not a reply. Missing LLM keys return a labeled
`source: fixture` draft. Never auto-send.

## Clerk types (do not invent names)

- `MoneyV2` = `{ amount: string, currencyCode: string }`
- `MoneyBag` = `{ shopMoney: MoneyV2, presentmentMoney?: MoneyV2 }`
- `numberOfOrders` is a JSON **string** (UnsignedInt64)
- `currentTotalPriceSet` is a **MoneyBag**, not MoneySet
- Customer email is `defaultEmailAddress.emailAddress` (never deprecated `Customer.email`)
- Line price is `originalUnitPriceSet.shopMoney`
- `sku` is `String | null`; omit the key when null (never print the word `null`)
- `billingAddress` null is real; peek/copy label is `No billing`
- `inProgress` is true iff any `returns.nodes[].status === "OPEN"` (`ReturnStatus`)
- `orderReturnStatus` is `Order.returnStatus` (`OrderReturnStatus`, live `NO_RETURN`)
- Do not treat `Order.returnStatus === "IN_PROGRESS"` as an OPEN return

## Live vs sample returns

Cute Things live shop has **zero** OPEN returns. The live MCP/CLI path must
return `{ orderReturnStatus: "NO_RETURN", returns: { nodes: [] }, inProgress: false }`.

One invented `OPEN` return exists on the **sample** catalog only (`demo-helpdesk.example`)
so UI/tests can review an in-progress return. That fixture is never injected
onto a live shop query.

## Auth

Reads use `SHOPIFY_SHOP`, `SHOPIFY_CLIENT_ID`, `SHOPIFY_CLIENT_SECRET`.
Mint reads shop from `SHOPIFY_SHOP` only (strip `https://`, trailing slash,
lowercase) and pins it to Cute Things (`yznyc1-ez.myshopify.com`). Unset or
any other host refuses mint. The token POST never follows 3xx redirects, so
the client secret is never sent to another host. Missing env or mint failure
falls back to labeled sample/live-hole fixtures. Tokens are never written to
disk or printed. `SHOPIFY_MUTATIONS_ENABLED` stays `0`; writes are refused.

Docs: [Customer](https://shopify.dev/docs/api/admin-graphql/2026-07/objects/Customer),
[Order](https://shopify.dev/docs/api/admin-graphql/2026-07/objects/Order),
[MoneyBag](https://shopify.dev/docs/api/admin-graphql/2026-07/objects/MoneyBag),
[ReturnStatus](https://shopify.dev/docs/api/admin-graphql/2026-07/enums/ReturnStatus),
[OrderReturnStatus](https://shopify.dev/docs/api/admin-graphql/2026-07/enums/OrderReturnStatus).
