# Spam filter — review shots

Local review: `console-src/inbox/run-review.sh` → `http://127.0.0.1:8766/`

| File | What it shows | URL |
|---|---|---|
| `01-spam-menu-selected.png` | Filter menu open, **Spam** selected, list is soft-hidden spam only | `/?view=spam&menu=1` |
| `02-spam-empty.png` | Empty Spam view mute copy: `No tickets in this view.` | `/?view=spam&empty=1&menu=1` |

`?empty=1` pins an empty catalog for review. It is not a product toggle.

Default boot without `?view=` is All (`all`).
Seed `t-pix-spam` is soft-hidden so the filtered list has a row.
