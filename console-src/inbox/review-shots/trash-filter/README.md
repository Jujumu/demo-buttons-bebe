# Trash filter — review shots

Local review: `console-src/inbox/run-review.sh` → `http://127.0.0.1:8766/`

| File | What it shows | URL |
|---|---|---|
| `01-trash-menu-selected.png` | Filter menu open, **Trash** selected, list is archived tickets only | `/?view=trash&menu=1` |
| `02-trash-empty.png` | Empty Trash view mute copy: `No tickets in this view.` | `/?view=trash&empty=1&menu=1` |

`?empty=1` pins an empty catalog for review. It is not a product toggle.

Default boot without `?view=` stays Assigned to me (`mine`).
Seed `t-nora-old` is archived so the filtered list has a row.
