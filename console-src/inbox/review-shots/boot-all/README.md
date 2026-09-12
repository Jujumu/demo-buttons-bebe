# Default boot All — review shots

Local review: `console-src/inbox/run-review.sh` → `http://127.0.0.1:8766/`

| File | What it shows | URL |
|---|---|---|
| `01-boot-all-menu-selected.png` | Filter menu open, **All** selected, list includes Closed and Snoozed rows | `/?menu=1` |
| `02-boot-mine-override.png` | `?view=mine` still selects **Assigned to me** and hides Closed / Snoozed | `/?view=mine&menu=1` |

Default boot without `?view=` is All (`all`). `?view=` still overrides.
