# Search toolbar row — review shots

Local review: `console-src/inbox/run-review.sh` → `http://127.0.0.1:8766/`

| File | What it shows | URL |
|---|---|---|
| `01-two-row-toolbar.png` | Row 1 Inbox + New ticket + sort/view tools. Row 2 full-width Search tickets | `/` |
| `02-search-clear.png` | `/?q=ada` hits plus the clear control on the full-width search row | `/?q=ada` |
| `03-search-empty.png` | `/?q=zzzz` list says **No matches.** Thread is `Select a ticket.` | `/?q=zzzz` |

Two-row chrome. Search stays inside the active view. No `data-view="search"`. No purple.
