# Gorgias bridge setup (detachable)

The demo helpdesk can sit beside the client's Gorgias. Gorgias stays the mailbox
of record. Our inbox drafts replies. The human clicks Send. A switch turns the
whole bridge off.

## Env keys

Copy into the host `.env` (never commit values):

```bash
# Detachable Gorgias bridge
GORGIAS_BRIDGE_ENABLED=0          # 1 = accept Gorgias webhooks + route replies via Gorgias
HELPDESK_OUTBOUND_ENABLED=0       # 1 = real Send leaves this host (needs auth or loopback)
HELPDESK_SEND_ALLOWLIST=          # comma emails for the pilot; empty = any recipient
GORGIAS_BRIDGE_SECRET=            # openssl rand -hex 32
GORGIAS_SUBDOMAIN=                # bare subdomain
GORGIAS_API_EMAIL=                # REST API username
GORGIAS_API_KEY=                  # REST API key
GORGIAS_BASE_URL=                 # optional; demo fake REST uses http://127.0.0.1:8190
AGENTMAIL_API_KEY=
# required for email route when bridge is OFF
HELPDESK_STORE_FILE=console-src/inbox/data/intake_tickets.json
HELPDESK_SEEN_FILE=console-src/inbox/data/seen_messages.json
```

Flip procedure: edit `GORGIAS_BRIDGE_ENABLED`, restart `helpdesk-inbox` (or the
review server). Webhooks return `503 bridge_disabled` when OFF. Send then uses
AgentMail email (or stays local if `HELPDESK_OUTBOUND_ENABLED=0`).

## Gorgias HTTP Integration

1. Gorgias → Settings → REST API → create a key (email + API key).
2. Settings → HTTP Integration → New.
3. Method: `POST`
4. URL: `https://helpdesk.teddyonfriday.com/webhook/gorgias`
   (or your tunnel / loopback via Caddy)
5. Header: `Authorization: Bearer <GORGIAS_BRIDGE_SECRET>`
   (Query-string secrets are rejected — they leak in logs.)
6. Trigger: **Ticket message created** only (`ticket-message-created`)
7. Body (JSON template):

```json
{
  "trigger": "ticket-message-created",
  "ticket": {
    "id": {{ticket.id}},
    "subject": {{ticket.subject|tojson}},
    "channel": {{ticket.channel|tojson}},
    "customer": {
      "email": {{ticket.customer.email|tojson}},
      "name": {{ticket.customer.name|tojson}}
    }
  },
  "message": {
    "id": {{message.id}},
    "from_agent": {{message.from_agent|tojson}},
    "body_text": {{message.body_text|tojson}},
    "channel": {{message.channel|tojson}},
    "created_datetime": {{message.created_datetime|tojson}},
    "sender": {{message.sender|tojson}}
  }
}
```

Agent messages (including our own replies) are ignored so Send does not echo.

## Caddy (example)

See [deploy/caddy/sites/helpdesk.caddy](caddy/sites/helpdesk.caddy). Allow
`POST /webhook/gorgias`. Put `/console/api/helpdesk` behind `forward_auth` to
the existing console login **before** setting `HELPDESK_OUTBOUND_ENABLED=1` on a
public host. Loopback-only is also fine for a pilot.

## Smoke test

1. Set allowlist to your own address. Enable both switches. Restart.
2. Email the client's Gorgias support address.
3. Confirm the ticket appears in our inbox (`source=gorgias`).
4. Send a reply → it lands on the Gorgias ticket and in your mailbox.
5. Set `GORGIAS_BRIDGE_ENABLED=0`, restart → webhook is 503; Send routes by email.
