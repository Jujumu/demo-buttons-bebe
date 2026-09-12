# Search empty clears thread — review shots

Local review: `console-src/inbox/run-review.sh` → `http://127.0.0.1:8766/`

| File | What it shows | URL |
|---|---|---|
| `01-search-empty-no-stale-thread.png` | All view. `/?q=zzzz` list says **No matches.** Thread is `Select a ticket.` not Ada. | `/?q=zzzz` |

Chrome, not a view. Held `selectedId` stays off screen until the query is cleared.
