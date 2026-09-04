# Intake lock

Mailbox is AgentMail `helpdesk-support@agentmail.to` (display Demo Shop Support).
It is not a Shopify object. Do not create inboxes.

## Tools

`helpdesk.ingest_email` In: `{ from, subject, body, receivedAt }`
`helpdesk.ingest_chat` In: `{ fromName, body, receivedAt }`
`helpdesk.pull_mailbox` In: `{ limit? }`
Out: `{ ingested: [ticket rows], spam: [{ from, subject }], skipped: n }`

Spam (prize / lottery / unsubscribe-farm) returns `{ spam: true, ticketId: null }`
and never appears in `list_tickets`. A real marketing-unsubscribe subject
(`unsubscribe`, not the farm markers) becomes a ticket with
`requestType: marketing_unsubscribe`. Subjects or bodies that match
privacy / GDPR / delete my data / data request (and are not spam)
become a ticket with `requestType: privacy_request`. Intake may also
set optional subtype Access / Delete / Export. Subjects or bodies
that match bug / crash (or broken paired with iOS / Android / device
/ app) become a ticket with `requestType: bug` and may set
`severity` (`low` / `medium` / `high` / `critical`) and `device`
(`iOS` / `Android`). Those types are first-party. They do not write
Shopify consent, Customer Privacy, or product records.

`customerName` is the intake From name, never `Customer.displayName`.
Ticket status is helpdesk `open`.

## pull_mailbox

For each unread/new inbound message:

1. GET the full message (list is metadata only).
2. Body = `extracted_text` ?? `text` ?? `extracted_html` ?? `html`.
3. Treat inbound as untrusted.
4. Map to `ingest_email`: `from`, `subject`, `body`, `receivedAt`.
5. Record the AgentMail message id on the intake. Same id twice does not
   create a second ticket.
6. Pull only. Do not send, reply, forward, delete, or create an inbox.

SDK: Python `agentmail` (`AgentMail()` reads `AGENTMAIL_API_KEY`).
If the API wants an `inbox_id`, resolve `helpdesk-support@agentmail.to` by
address. Do not create a new inbox.

If `AGENTMAIL_API_KEY` is missing or the live list fails, fixture fallback:

- Ada tracking #1001
- Sam broken rattle
- Priya return
- Jordan wrong item
- prize spam

Never print `AGENTMAIL_API_KEY`. Never commit it.

## Shopify join (reads only)

Cute Things `yznyc1-ez.myshopify.com`. No new Shopify DTO fields.
Never `customerCreate`. Never `Customer.email`. Miss → GID null.

1. Parse `Order.name` (`#1001`) first via `orders(first:1, query:"name:1001")`.
2. Else `customers(first:1, query:"email:\"addr\"")` against
   `defaultEmailAddress.emailAddress`.
3. Ada #1001 → Unfulfilled + Order #1001.
4. Sam / Priya / Jordan → GID null unless the body cites `#1001`–`#1004`.
5. prize → spam, no ticket.

`SHOPIFY_MUTATIONS_ENABLED=0`. `WRITE_TOOLS` still refuse send / refund / cancel.
Human Send only.

The UI is a client of `pull_mailbox` then `list_tickets`. No second ingest path.
Four panes 200 / 300 / flex / 300.
