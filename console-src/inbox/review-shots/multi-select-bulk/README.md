# Multi-select + bulk — review shots

Local review: `console-src/inbox/run-review.sh` → `http://127.0.0.1:8766/`

| File | What it shows | URL |
|---|---|---|
| `01-selection-bar.png` | All view. Ink checkboxes. Selection bar reads **All selected** | `/?select=1` |
| `02-bulk-menu.png` | Same selection. Actions menu open: Mark as read, Mark as unread, Assign, Snooze, Delete | `/?select=1&bulk=1` |

V1 only. No Add tag, Assign to team, Change priority, Export, or Apply macro.
Ink / accent. No purple. Delete is Trash (`archived`), not a Shopify delete.
