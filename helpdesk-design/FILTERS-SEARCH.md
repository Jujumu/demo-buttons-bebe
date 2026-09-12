# Filters + search — LOCK addendum

First-party list filters only. No new Shopify Admin fields. No Cute Things
writes. Mute words, never color-alone. Four panes / three chrome stay.
Human Send. `WRITE_TOOLS` untouched. Gorgias off.

This file is the thin addendum for list-toolbar filters. Bug severity
sub-filters (High / Critical) are first-party view ids on the Bug pile.

## Default boot (this slice)

Default chrome is **All** (`all`). `?view=` still overrides
(`mine` / `open` / `escalated` / `unsubscribe` / `privacy` / `bug` /
`bug_high` / `bug_critical` / `trash` / `spam` / other view ids).

## Open (shipped)

`helpdesk.list_tickets` accepts `{ view: "open" }` on the same
`dispatch()` / `invoke()` path as MCP + CLI.

1. **Open** list view filters tickets where first-party
   `status === "open"`. Snoozed and Closed stay out.
2. Menu order starts Assigned to me · Unassigned · Open · Escalated ·
   Unsubscribe · Privacy · Bug · High · Critical · All · Snoozed ·
   Closed · Trash · Spam.
3. Default boot is **All** (`all`). `?view=open` is the
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

## Escalated (shipped)

Ticket already has first-party `escalated` and optional `escalationReason`
from `helpdesk.escalate_ticket`. `get_ticket` already projects both.
List `_row` stays thin and omits `escalated`.

1. **Escalated** list view id is `escalated`. `ticket_in_view` is true
   when `bool(ticket.get("escalated"))`. Status is not a constraint.
   Closed or snoozed tickets that are escalated still match.
2. Add **Escalated** to the list toolbar filter menu after Open.
3. Default boot is **All** (`all`). `?view=escalated` is
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

## Unsubscribe / Privacy / Bug (this slice)

First-party ticket `requestType` only. Not a Shopify Marketing,
Customer Privacy / GDPR, or catalog write. Mute badges stay mute.

1. **Unsubscribe** view id is `unsubscribe`. `ticket_in_view` is true
   when `requestType === "marketing_unsubscribe"`. Status is not a
   constraint.
2. **Privacy** view id is `privacy`. Match `requestType ===
   "privacy_request"`.
3. **Bug** view id is `bug`. Match `requestType === "bug"`. Keep the
   mute Bug + severity chips.
4. Add the three labels to the list toolbar filter menu after
   Escalated. Archived and spam tickets stay out (same as Escalated).
5. Default boot is **All** (`all`). Review URLs:
   `/?view=unsubscribe&menu=1`, `/?view=privacy&menu=1`,
   `/?view=bug&menu=1`. Empty catalogs use `?empty=1`.
6. Empty copy stays `No tickets in this view.`
7. Agent-native: `list_tickets({ view: "unsubscribe" | "privacy" |
   "bug" })` on the same `dispatch()` path. CLI:
   `helpdesk list-tickets --view unsubscribe`. WebMCP `select_view`
   lists the three ids.

Seeds: Priya `t-priya-unsub`, Lee `t-lee-privacy`, Remy `t-remy-bug`.

## Bug High / Critical (this slice)

First-party ticket `severity` on `requestType === "bug"` only. Not a
global Priority view. Not a Shopify Admin priority field.

1. **High** view id is `bug_high`. `ticket_in_view` is true when
   `requestType === "bug"` and `_normalize_severity(severity) ===
   "high"`. Status is not a constraint. Archived and spam tickets stay
   out.
2. **Critical** view id is `bug_critical`. Match `requestType ===
   "bug"` and `_normalize_severity(severity) === "critical"`.
3. Add **High** and **Critical** to the list toolbar filter menu after
   Bug. Labels are the severity words. Mute selected ink edge, same as
   siblings. Do not add Low or Medium menu items.
4. Default boot is **All** (`all`). Review URLs:
   `/?view=bug_high&menu=1`, `/?view=bug_critical&menu=1`. Empty
   catalogs use `?empty=1`.
5. Empty copy stays `No tickets in this view.`
6. Agent-native: `list_tickets({ view: "bug_high" | "bug_critical" })`
   on the same `dispatch()` path. CLI:
   `helpdesk list-tickets --view bug_high`. WebMCP `select_view` lists
   both ids.
7. The Bug view still lists every non-archived, non-spam bug.

Seeds: Remy `t-remy-bug` (high, escalated), Kit `t-kit-critical`
(critical, not escalated). Escalated stays Remy-only.

## Trash (shipped)

Ticket gains first-party `archived` (soft-archive). This is not Closed
status and not a Shopify delete. List `_row` stays thin and omits
`archived`. `get_ticket` projects it.

1. **Trash** list view id is `trash`. `ticket_in_view` is true when
   `bool(ticket.get("archived"))`.
2. Archived tickets stay out of All, Assigned to me, Unassigned, Open,
   Escalated, Unsubscribe, Privacy, Bug, High, Critical, Snoozed, and
   Closed. They appear only under Trash.
3. Add **Trash** to the list toolbar filter menu after Closed.
4. Default boot is **All** (`all`). `?view=trash` is the
   Trash queue. `?view=trash&empty=1` pins an empty catalog.
5. Rows have no Trash chip. Empty copy stays `No tickets in this view.`
6. Agent-native: `list_tickets({ view: "trash" })` on the same
   `dispatch()` path. CLI: `helpdesk list-tickets --view trash`.
   WebMCP `select_view` lists `trash`.

Seed `t-nora-old` is archived in both the Python sample store and the
JS demo fixtures so the queue is reviewable. Status stays `open` so
the hide from Open / Assigned to me is visible.

## Spam (this slice)

Ticket gains first-party `spam` (Gorgias-like soft-hide). This is not a
Shopify Admin spam API, not a hard delete, and not the intake prize
reject (`{ spam: true, ticketId: null }`, no ticket). List `_row` stays
thin and omits `spam`. `get_ticket` projects it.

1. **Spam** list view id is `spam`. `ticket_in_view` is true when
   `bool(ticket.get("spam"))`.
2. Spam tickets stay out of All, Assigned to me, Unassigned, Open,
   Escalated, Unsubscribe, Privacy, Bug, High, Critical, Snoozed,
   Closed, and Trash.
   They appear only under Spam.
3. Trash and Spam are separate piles. If both flags are set, spam wins:
   the ticket is in Spam and out of Trash.
4. Add **Spam** to the list toolbar filter menu after Trash. Mute word
   only. No purple badge.
5. Default boot is **All** (`all`). `?view=spam` is the
   Spam queue. `?view=spam&empty=1` pins an empty catalog.
6. Rows have no Spam chip. Empty copy stays `No tickets in this view.`
7. Agent-native: `list_tickets({ view: "spam" })` on the same
   `dispatch()` path. CLI: `helpdesk list-tickets --view spam`.
   WebMCP `select_view` lists `spam`.

Seed `t-pix-spam` is soft-hidden in both the Python sample store and the
JS demo fixtures so the queue is reviewable. Status stays `open` so the
hide from Open / Assigned to me is visible. Intake still drops prize /
lottery mail before a ticket exists.

## Unread (this slice)

First-party list chrome only. Not a view. No Shopify Admin field.

1. Distinguish read vs unread in the ticket list (Gorgias red-dot intent,
   our chrome). Unread: **bold** customer name plus a small **ink** mark.
   Not purple. Not red-alone. Never color-alone.
2. Read: regular weight, no mark.
3. Opening a ticket marks it read for this session.
4. Do not add Unread to the filter menu.
5. Review unread vs read rows on default All (`/`). Opening a second
   ticket is `/?ticket=t-priya-unsub`.

## Multi-select + bulk (this slice)

First-party list chrome. No Shopify Admin field. No Cute Things write.

1. Row checkboxes plus a selection bar. Copy is **All selected** when every
   visible row is checked, else `N selected`. Ink / accent only. Not purple.
2. V1 bulk menu on the bar: Mark as read · Mark as unread · Assign
   (Agent / Unassigned) · Snooze · Delete. Delete sets first-party
   `archived` (Trash). It does not hard-delete and does not write Shopify.
3. Read / unread stay session-local from Unread. Assign writes first-party
   `assignee` (`me` or unassigned). Snooze sets helpdesk `status` to
   `snoozed`. Same `dispatch()` path as MCP + CLI:
   `helpdesk.bulk_update_tickets`.
4. Do not ship Add tag, Assign to team, Change priority, Export tickets,
   or Apply macro.
5. Review selection + menu with `/?select=1&bulk=1`.

## New ticket (this slice)

First-party list chrome. No Shopify Customer or Order create.

1. **New ticket** control in the list toolbar next to Inbox / Search /
   filter. Mute / ink / line only. Not purple.
2. Click (or optional `N` when not typing) creates an empty first-party
   ticket and selects it. Compose focuses. Thread has no inbound
   messages. Rail stays `No customer` / `No order`.
3. `helpdesk.create_ticket` on the same `dispatch()` path as MCP + CLI.
   In `{}`. Out is a Clerk ticket with null GIDs and `source: compose`.
   Human still sends.
4. Review with `/?new=1`.

## Search (this slice)

First-party list chrome only. Not a view. No Shopify Admin field.

1. Search field in the list toolbar next to filter/sort. Placeholder
   **Search tickets**. Ink / mute / line only. Not purple.
2. Narrows the current view. Case-insensitive substring on customer
   name, subject, snippet, and id. Empty query shows the view.
3. Empty copy is **No matches.** when the query has no hits. Empty
   view copy stays `No tickets in this view.`
4. When the filtered list is empty, hide the previously selected
   thread and composer. Thread copy stays `Select a ticket.`
   Composer copy stays `Select a ticket to reply.` Keep the held
   `selectedId`. Clearing the query restores that ticket.
5. Do not add Search to the filter menu. No `data-view="search"`.
   No `list_tickets` `q`.
6. Review hits with `/?q=ada`. Empty with `/?q=zzzz`.

## Out of this PR

Do not add Low or Medium severity menu items.
Do not ship a global Priority view.
Do not ship Unread as a Views menu item.
Do not ship Add tag, Assign to team, Change priority, Export, or Apply macro.
Do not fold Bug severity into this search-empty slice.
