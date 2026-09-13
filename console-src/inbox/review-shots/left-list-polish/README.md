# Left list polish — review shots

Local review: `console-src/inbox/run-review.sh` → `http://127.0.0.1:8766/`

Lock: `helpdesk-design/FILTERS-SEARCH.md` Polish + fixtures 2026-09-13.
Playground before: https://helpdesk.srv804603.hstgr.cloud @ 4ab89c5

| File | What it shows | URL |
|---|---|---|
| `01-new-ticket-untitled.png` | New ticket row name is **Untitled**, not New ticket. Subject may stay New ticket | `/?new=1` |
| `02-unread-ink-mark.png` | Unread rows: bold name + small **ink** mark. No blue / red / purple dots | `/` |
| `03-search-clear-empty.png` | Search empty: no `×` in the field. Filter / sort sit outside, ≥40px | `/` |
| `04-search-clear-query.png` | `/?q=ada`: clear `×` visible. Filter / sort still outside the field | `/?q=ada` |
| `05-row-status-pill.png` | Jordan row: relative time + mute **Snoozed** pill, not floating plain text | `/?ticket=t-jordan-ship` |
| `06-selected-ink-bar.png` | Selected row: soft ink tint **and** 4px ink leading bar. Not purple | `/` |

Paper cream + IBM Plex. List pane only. Thread and rail stay.
No Pending / Waiting / Starred. No Gorgias purple.
