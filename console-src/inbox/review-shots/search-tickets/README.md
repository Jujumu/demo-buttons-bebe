# Search tickets — review shots

Local review: `console-src/inbox/run-review.sh` → `http://127.0.0.1:8766/`

| File | What it shows | URL |
|---|---|---|
| `01-search-hits.png` | All view. `/?q=ada` hits plus the clear control | `/?q=ada` |
| `02-search-empty.png` | All view. `/?q=zzzz` empty pane **No matches.** | `/?q=zzzz` |

Chrome, not a view. No `data-view="search"`. No purple.
