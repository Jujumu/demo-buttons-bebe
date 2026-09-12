# Escalated filter — review shots

Local review: `console-src/inbox/run-review.sh` → `http://127.0.0.1:8766/`

| File | What it shows | URL |
|---|---|---|
| `01-escalated-menu-selected.png` | Filter menu open, **Escalated** selected, list is escalated tickets only | `/?view=escalated&menu=1` |
| `02-escalated-empty.png` | Empty Escalated view mute copy: `No tickets in this view.` | `/?view=escalated&empty=1&menu=1` |

`?empty=1` pins an empty catalog for review. It is not a product toggle.

Default boot without `?view=` is All (`all`).
 Seed `t-remy-bug` is escalated so the filtered list has a row.
