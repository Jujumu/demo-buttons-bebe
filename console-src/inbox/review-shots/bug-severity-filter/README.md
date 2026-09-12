# Bug severity filters — review shots

Local review: `console-src/inbox/run-review.sh` → `http://127.0.0.1:8766/`

| File | What it shows | URL |
|---|---|---|
| `01-high-menu-selected.png` | Filter menu open, **High** selected, list is `requestType === "bug"` and severity high (Remy). Mute Bug + High badges. | `/?view=bug_high&menu=1` |
| `02-critical-menu-selected.png` | Filter menu open, **Critical** selected, list is `requestType === "bug"` and severity critical (Kit). Mute Bug + Critical badges. | `/?view=bug_critical&menu=1` |
| `03-high-empty.png` | Empty High view mute copy: `No tickets in this view.` | `/?view=bug_high&empty=1&menu=1` |
| `04-critical-empty.png` | Empty Critical view mute copy: `No tickets in this view.` | `/?view=bug_critical&empty=1&menu=1` |

`?empty=1` pins an empty catalog for review. It is not a product toggle.

Default boot without `?view=` is All (`all`).
Seed `t-remy-bug` is a high-severity bug so High has a row.
Seed `t-kit-critical` is a critical-severity bug so Critical has a row.
First-party `requestType` / `severity` only. No Shopify catalog write.
No Low / Medium menu items.
