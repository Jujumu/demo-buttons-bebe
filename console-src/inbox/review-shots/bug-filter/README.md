# Bug filter — review shots

Local review: `console-src/inbox/run-review.sh` → `http://127.0.0.1:8766/`

| File | What it shows | URL |
|---|---|---|
| `01-bug-menu-selected.png` | Filter menu open, **Bug** selected, list is `requestType === "bug"` only (Remy). Mute Bug + High badges. | `/?view=bug&menu=1` |
| `02-bug-empty.png` | Empty Bug view mute copy: `No tickets in this view.` | `/?view=bug&empty=1&menu=1` |

`?empty=1` pins an empty catalog for review. It is not a product toggle.

Default boot without `?view=` is All (`all`).
Seed `t-remy-bug` is a high-severity bug so the filtered list has a row.
First-party `requestType` / `severity` only. No Shopify catalog write.
No High / Critical sub-filters in this slice.
