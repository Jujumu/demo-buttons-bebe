# Filters + search — LOCK addendum

First-party list filters only. No new Shopify Admin fields. No Cute Things
writes. Mute words, never color-alone. Four panes / three chrome stay.
Human Send. `WRITE_TOOLS` untouched. Gorgias off.

This file is the thin addendum for list-toolbar filters. Do not ship
Escalated, request-type, severity, Trash, Spam, or Search from this
document — those wait for later slices.

## Open (this slice)

`helpdesk.list_tickets` already accepts `{ view: "open" }` on the same
`dispatch()` / `invoke()` path as MCP + CLI. Status already exists.
The list toolbar menu was missing **Open**.

1. **Open** list view filters tickets where first-party
   `status === "open"`. Snoozed and Closed stay out.
2. Add **Open** to the list toolbar filter menu. Keep existing:
   Assigned to me · Unassigned · All · Snoozed · Closed.
   Menu order: Assigned to me · Unassigned · Open · All · Snoozed · Closed.
3. Default boot stays **Assigned to me** (`mine`). `?view=open` is the
   Open queue. If boot still defaults to `open`, fix it in the Open
   filter PR when that change is cheap.
4. In the Open queue, omit the repeating Open status chip on rows
   (main `LOCK.md`). Keep Closed / Snoozed chips in those queues.
5. Empty filtered list copy stays the existing mute line:
   `No tickets in this view.` Review empty Open with `?view=open&empty=1`
   (pins an empty catalog; not a product toggle). Open the filter menu
   for shots with `?menu=1` (clicks the existing Views control).
6. Agent-native: wire Open through `list_tickets({ view })` on the same
   `dispatch()` path. CLI: `helpdesk list-tickets --view open`. WebMCP
   `select_view` already lists `open`.

## Out of this PR

Do not add Escalated, request-type, severity, Trash, Spam, or Search
chrome here.
