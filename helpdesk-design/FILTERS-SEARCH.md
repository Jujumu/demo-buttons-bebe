# Filters + search — LOCK addendum

First-party list filters only. No new Shopify Admin fields. No Cute Things
writes. Mute words, never color-alone. Four panes / three chrome stay.
Human Send. `WRITE_TOOLS` untouched. Gorgias off.

This file is the thin addendum for list-toolbar filters. Do not ship
request-type, severity, Trash, Spam, or Search from this document —
those wait for later slices.

## Open (shipped)

`helpdesk.list_tickets` accepts `{ view: "open" }` on the same
`dispatch()` / `invoke()` path as MCP + CLI.

1. **Open** list view filters tickets where first-party
   `status === "open"`. Snoozed and Closed stay out.
2. Menu order starts Assigned to me · Unassigned · Open · Escalated ·
   All · Snoozed · Closed.
3. Default boot stays **Assigned to me** (`mine`). `?view=open` is the
   Open queue.
4. In the Open queue, omit the repeating Open status chip on rows
   (main `LOCK.md`). Keep Closed / Snoozed chips in those queues.
5. Empty filtered list copy stays the existing mute line:
   `No tickets in this view.` Review empty Open with `?view=open&empty=1`
   (pins an empty catalog; not a product toggle). Open the filter menu
   for shots with `?menu=1` (clicks the existing Views control).
6. Agent-native: `list_tickets({ view })` on the same `dispatch()` path.
   CLI: `helpdesk list-tickets --view open`. WebMCP `select_view` lists
   `open`.

## Escalated (this slice)

Ticket already has first-party `escalated` and optional `escalationReason`
from `helpdesk.escalate_ticket`. `get_ticket` already projects both.
List `_row` stays thin and omits `escalated`.

1. **Escalated** list view id is `escalated`. `ticket_in_view` is true
   when `bool(ticket.get("escalated"))`. Status is not a constraint.
   Closed or snoozed tickets that are escalated still match.
2. Add **Escalated** to the list toolbar filter menu after Open.
3. Default boot stays **Assigned to me** (`mine`). `?view=escalated` is
   the Escalated queue. `?view=escalated&empty=1` pins an empty catalog.
4. Rows have no Escalated chip today (main `LOCK.md` and
   `docs/tissues/inbox.md`). The Escalated queue omits repeating
   Escalated row chrome if any appears later.
5. Empty copy stays `No tickets in this view.`
6. Agent-native: `list_tickets({ view: "escalated" })` on the same
   `dispatch()` path. CLI: `helpdesk list-tickets --view escalated`.
   WebMCP `select_view` lists `escalated`.

Seed `t-remy-bug` is escalated in both the Python sample store and the
JS demo fixtures so the queue is reviewable. `t-ada-track` stays
unescalated until `escalate_ticket` runs.

## Out of this PR

Do not add request-type, severity, Trash, Spam, or Search chrome here.
