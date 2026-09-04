# Helpdesk organ — tissue contracts

Agent-native organ. The UI is a client. Every tissue is a black box
(`In → Out`) exposed as an MCP tool and a CLI command on the **same handler**.

This organ does **not** wrap Gorgias. Ticket tissues are first-party.
Shopify rail tissues speak Admin GraphQL **2026-07** field names only.

## Tools (v1, fifteen)

Six rail/inbox reads, two Caduceus composer tools, two macro tools, two
intake tools, one AgentMail pull, first-party `escalate_ticket`, and
`write_gate_status`. Composer and macro tools return text.
They never send, refund, or cancel. Intake writes a first-party ticket (or
drops spam). It never creates a Shopify customer. `pull_mailbox` reads the
AgentMail inbox and calls `ingest_email`. It never sends, replies, forwards,
deletes, or creates an inbox. `escalate_ticket` is first-party helpdesk
state (escalated/pending). It is not a Shopify mutation.

| Tool | Tissue | CLI | In | Out |
|---|---|---|---|---|
| `helpdesk.list_tickets` | list | `helpdesk list-tickets` | `{ view, limit }` | ticket rows (`id`, `customerName`, `subject`, `snippet`, `status`, `updatedAt`, `customerId`, `orderId`, `requestType`) |
| `helpdesk.get_ticket` | thread | `helpdesk get-ticket` | `{ ticketId }` | ticket + `messages` + `statusEvents` + `requestType`. Each message carries `from` (`customer`/`agent`), `fromName`, and optional `fromEmail`. Inbound From is the customer persona, never the mailbox login. |
| `helpdesk.get_customer` | customer | `helpdesk get-customer` | `{ shop, customerId }` GID | `ClerkCustomer` |
| `helpdesk.get_order` | order | `helpdesk get-order` | `{ shop, orderId }` GID | `ClerkOrder` |
| `helpdesk.get_returns` | returns | `helpdesk get-returns` | `{ shop, orderId }` GID | returns payload |
| `helpdesk.list_past_orders` | order-history | `helpdesk list-past-orders` | `{ shop, customerId }` GID | `ClerkOrderHistoryRow[]` newest first |
| `helpdesk.draft_reply` | composer draft | `helpdesk draft-reply --ticket …` | `{ ticketId, shop?, thread?, rail DTOs? }` | `{ draft }` for Insert/Discard |
| `helpdesk.summarize_thread` | composer peek | `helpdesk summarize-thread --ticket …` | `{ ticketId, thread? }` | `{ summary }` mute peek, never a send |
| `helpdesk.search_macros` | composer macros | `helpdesk search-macros --query …` | `{ query? }` | `{ macros: [{ id, title, body, tags }] }` |
| `helpdesk.apply_macro` | composer insert | `helpdesk apply-macro --macro-id … --mode replace\|append` | `{ macroId, mode?, currentBody? }` | `{ text, title, mode, body }` for the textarea |
| `helpdesk.ingest_email` | intake | `helpdesk ingest-email` | `{ from, subject, body, receivedAt }` | signed ticket row, or `{ spam: true, ticketId: null }` |
| `helpdesk.ingest_chat` | intake | `helpdesk ingest-chat` | `{ fromName, body, receivedAt }` | signed ticket row, or `{ spam: true, ticketId: null }` |
| `helpdesk.pull_mailbox` | mailbox | `helpdesk pull-mailbox` | `{ limit? }` | `{ ingested: [ticket rows], spam: [{ from, subject }], skipped: n }` |
| `helpdesk.escalate_ticket` | thread escalate | `helpdesk escalate-ticket` | `{ ticketId, reason? }` | ticket + `escalated: true` (status stays open/closed/snoozed) |
| `helpdesk.write_gate_status` | write gate | `helpdesk write-gate-status` | `{}` | `{ mutationsEnabled, refused: ["send","refund","cancel"], tools }` |

**Macro contract.** `search_macros` always returns the fixture body so a client
can insert without a second call. `apply_macro` is the insert path: `replace`
overwrites the box, `append` adds after existing text. Neither tool sends.
The human still hits Send. Fixtures (offline): Shipping delay, Return how-to,
Order status.

No `helpdesk.send`, `helpdesk.refund`, or `helpdesk.cancel`. Those stay in
`WRITE_TOOLS` and are refused. `SHOPIFY_MUTATIONS_ENABLED` stays `0`.
MCP `tools/list` documents the refused write tools with a `REFUSED`
description. Agents can also call `helpdesk.write_gate_status` or invoke a
write tool and read `{ ok: false, error: "forbidden", details: { refused, mutationsEnabled } }`.
Do not implement live refund or cancel.

Mailbox is AgentMail `helpdesk-support@agentmail.to` (display Demo Shop
Support). It is not a Shopify object. Prize/lottery/unsubscribe-farm copy is
spam and never becomes a ticket (`list_tickets` will not show it).

Shopify join is Cute Things reads only (`yznyc1-ez.myshopify.com`, Admin
GraphQL 2026-07). Parse `Order.name` from subject/body (`#1001`) first; else
match `fromEmail` to `Customer.defaultEmailAddress.emailAddress`. Chat has no
email, so order-name only. Miss → GID null. Never `customerCreate`. Never
deprecated `Customer.email`. `customerName` is the intake From name, never
`Customer.displayName`. Ticket status is helpdesk `open`.

The inbox is a client of these fifteen tools. MCP, CLI, and
`POST /console/api/helpdesk` (`{ tool, arguments }`) share `invoke()`.
The UI must not open a second GraphQL client. After `pull_mailbox`,
`list_tickets` shows the new rows. There is no second ingest path.

Rail IDs are Shopify GIDs (`gid://shopify/Customer/…`, `gid://shopify/Order/…`),
not bare ticket numbers. `list_tickets` / `get_ticket` attach those GIDs so the
rail can load when a row is selected. Ticket status is first-party
(`open` / `closed` / `snoozed`) — not `Return.status` and not
`Order.displayFulfillmentStatus`. `customerName` is first-party — never
`Customer.displayName`. Ticket tissues keep `{ view, limit }` / `{ ticketId }`.
`requestType` is first-party (`marketing_unsubscribe` /
`privacy_request` or `null`). It is not a Shopify consent or Customer
Privacy field. Intake subjects that contain `unsubscribe` (and are not
unsubscribe-farm spam) set marketing unsubscribe. Subjects or bodies
that match privacy / GDPR / delete my data / data request set privacy
request and may set subtype Access / Delete / Export. Human handles
both out of band. `privacyHandled` is a first-party ticket flag only.
Do not call marketing unsubscribe or Customer privacy / GDPR /
data-request Admin mutations.
Composer `--ticket` is the ticket id (sample `1001` aliases `t-ada-track`).

Drafts are merchant replies the human Inserts or Discards. Summaries are a
short mute peek of the thread, not a reply. Missing LLM keys return a labeled
`source: fixture` draft (Ada / demo names only). The greeting uses ticket
`customerName`, never `Customer.displayName`. Never auto-send.

## Clerk types (do not invent names)

- `MoneyV2` = `{ amount: string, currencyCode: string }`
- `MoneyBag` = `{ shopMoney: MoneyV2, presentmentMoney?: MoneyV2 }`
- `numberOfOrders` is a JSON **string** (UnsignedInt64)
- `currentTotalPriceSet` is a **MoneyBag**, not MoneySet
- Customer email is `defaultEmailAddress.emailAddress` (never deprecated `Customer.email`)
- Line price is `originalUnitPriceSet.shopMoney`
- `sku` is `String | null`; omit the key when null (never print the word `null`)
- `billingAddress` null is real; peek/copy label is `No billing`
- empty `fulfillments` / no `trackingInfo`: peek/copy label is `No tracking`. Do not invent a number. Tracking chrome is company + number as copy and a separate Track URL when present.
- `LineItem.unfulfilledQuantity` is official; omit when missing. Do not invent a line status.
- `Fulfillment.displayStatus` is official (`IN_TRANSIT`, …). `fulfillmentLineItems.nodes[].quantity` + `lineItem.title` are official when a shipment names its lines.
- `Order.displayFulfillmentStatus` includes `PARTIALLY_FULFILLED` for mixed ship.
- `Order.discountCodes` is official `[String!]`. Empty list when none. Do not invent `discounts[]`.
- `invoiceUrl` is a helpdesk DTO (`string | null`). Admin GraphQL 2026-07
  [`Order`](https://shopify.dev/docs/api/admin-graphql/2026-07/objects/Order)
  has **no** invoice/receipt URL field. Nearby official pieces we did **not**
  guess onto Order: [`DraftOrder.invoiceUrl`](https://shopify.dev/docs/api/admin-graphql/2026-07/objects/DraftOrder)
  (checkout link on a draft, not a paid-order receipt) and mutation
  [`orderInvoiceSend`](https://shopify.dev/docs/api/admin-graphql/2026-07/mutations/orderInvoiceSend)
  (write — refused). Live `get_order` returns `invoiceUrl: null` and does
  not query an invented field. Fixture Ada has an example `https://` URL.
  Clerk: wire an official Order document URL if/when 2026-07 grows one.
  Do not map `statusPageUrl` as an invoice.
- `warranty` is a helpdesk DTO (`{ period, status, endsOn } | null`).
  Admin GraphQL 2026-07
  [`Order`](https://shopify.dev/docs/api/admin-graphql/2026-07/objects/Order)
  and
  [`LineItem`](https://shopify.dev/docs/api/admin-graphql/2026-07/objects/LineItem)
  have **no** warranty field. Nearby official pieces we did **not** guess
  onto Order: Product/variant metafields (shop-chosen namespace/key — do not
  invent names). Live `get_order` returns `warranty: null` and does not query
  an invented field or metafield. Fixture Ada has `{ period: "1 year",
  status: "Active", endsOn: "2027-03-12" }`. Clerk: if live warranty is
  needed later, sign a metafield namespace/key after the shop defines one.
- `eta` is a helpdesk DTO (`string | null`, ISO date). Sourced from official
  [`Fulfillment.estimatedDeliveryAt`](https://shopify.dev/docs/api/admin-graphql/2026-07/objects/Fulfillment)
  (DateTime) on the first fulfillment that has one. Fixture Ada may also set
  a top-level `eta` when fulfillments are empty. Live `get_order` queries
  `fulfillments { estimatedDeliveryAt }` and returns null when Shopify has
  none. Do not invent a day.
- `shippingZone` is a helpdesk DTO (`string | null`). Admin GraphQL 2026-07
  [`Order`](https://shopify.dev/docs/api/admin-graphql/2026-07/objects/Order)
  and
  [`Fulfillment`](https://shopify.dev/docs/api/admin-graphql/2026-07/objects/Fulfillment)
  have **no** shipping-zone field. Nearby official pieces we did **not**
  guess onto Order: [`DeliveryLocationGroupZone`](https://shopify.dev/docs/api/admin-graphql/2026-07/objects/DeliveryLocationGroupZone)
  (profile zone, not an order) and [`ShippingLine.deliveryCategory`](https://shopify.dev/docs/api/admin-graphql/2026-07/objects/ShippingLine)
  (method class, not a zone name). Live `get_order` returns
  `shippingZone: null` and does not query an invented field. Fixture Ada
  has `Domestic`. Clerk: if live zone is needed later, sign the official
  Order/Fulfillment path after 2026-07 grows one.
- `inProgress` is true iff any `returns.nodes[].status === "OPEN"` (`ReturnStatus`)
- `orderReturnStatus` is `Order.returnStatus` (`OrderReturnStatus`, live `NO_RETURN`)
- Do not treat `Order.returnStatus === "IN_PROGRESS"` as an OPEN return
- Fixture `giftCards[]` on `ClerkCustomer` uses official `GiftCard` fields only:
  `id`, `lastCharacters`, `maskedCode`, `enabled`, `balance` (MoneyV2).
  Live `get_customer` does not query gift cards (Customer has no `giftCards`
  connection; Cute Things may lack `read_gift_cards`). Live returns `[]`.
  Clerk follow-up if live balances are needed: second read
  `giftCards(first: 20, query: "customer_id:<numeric id>")`.
  Do not invent `Order.giftCards`. Do not add giftCardCreate / giftCardDeactivate.

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
[Fulfillment](https://shopify.dev/docs/api/admin-graphql/2026-07/objects/Fulfillment),
[FulfillmentDisplayStatus](https://shopify.dev/docs/api/admin-graphql/2026-07/enums/FulfillmentDisplayStatus),
[LineItem](https://shopify.dev/docs/api/admin-graphql/2026-07/objects/LineItem),
[ReturnStatus](https://shopify.dev/docs/api/admin-graphql/2026-07/enums/ReturnStatus),
[OrderReturnStatus](https://shopify.dev/docs/api/admin-graphql/2026-07/enums/OrderReturnStatus),
[GiftCard](https://shopify.dev/docs/api/admin-graphql/2026-07/objects/GiftCard),
[giftCards query](https://shopify.dev/docs/api/admin-graphql/2026-07/queries/giftCards).
