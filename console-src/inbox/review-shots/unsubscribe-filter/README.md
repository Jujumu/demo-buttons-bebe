# Unsubscribe filter — review shots

Local review: `console-src/inbox/run-review.sh` → `http://127.0.0.1:8766/`

| File | What it shows | URL |
|---|---|---|
| `01-unsubscribe-menu-selected.png` | Filter menu open, **Unsubscribe** selected, list is `requestType === "marketing_unsubscribe"` only (Priya). Mute Unsubscribe badge. | `/?view=unsubscribe&menu=1` |
| `02-unsubscribe-empty.png` | Empty Unsubscribe view mute copy: `No tickets in this view.` | `/?view=unsubscribe&empty=1&menu=1` |

`?empty=1` pins an empty catalog for review. It is not a product toggle.

Default boot without `?view=` is All (`all`).
Seed `t-priya-unsub` is a marketing unsubscribe so the filtered list has a row.
First-party `requestType` only. No Shopify Marketing write.
