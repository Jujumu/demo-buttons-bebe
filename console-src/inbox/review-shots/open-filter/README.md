# Open filter — review shots

Local review: `console-src/inbox/run-review.sh` → `http://127.0.0.1:8766/`

| File | What it shows | URL |
|---|---|---|
| `01-open-menu-selected.png` | Filter menu open, **Open** selected, list is open tickets only (no Closed / Snoozed rows, no repeating Open chip) | `/?view=open&menu=1` |
| `02-open-empty.png` | Empty Open view mute copy: `No tickets in this view.` | `/?view=open&empty=1&menu=1` |

`?empty=1` pins an empty catalog for review. It is not a product toggle.

Default boot without `?view=` stays Assigned to me (`mine`).
