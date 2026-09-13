# Left list chrome — review shots

Local review: `console-src/inbox/run-review.sh` → `http://127.0.0.1:8766/`

Lock: `helpdesk-design/FILTERS-SEARCH.md` Left list chrome 2026-09-13.
Reference layout: `helpdesk-design/refs/left-list-chrome-2026-09-13.png`
Playground before: https://helpdesk.srv804603.hstgr.cloud

| File | What it shows | URL |
|---|---|---|
| `01-header-inbox-count-new.png` | Inbox + count badge. Accent **+ New ticket** on the right | `/` |
| `02-chips-open-selected.png` | Primary chips. **Open** selected (ink tint + ink label) | `/?view=open` |
| `03-search-filter-row.png` | Search tickets full width + More views filter | `/?q=ada` |
| `04-row-selected-ink-bar.png` | Checkbox · avatar initial · name/subject/snippet · time + pill. Selected soft tint + 4px ink bar | `/` |

Paper cream + IBM Plex + ink selection. No Pending / Waiting / Starred. No purple.
Thread and rail stay. PR 54 searchMiss stays.
