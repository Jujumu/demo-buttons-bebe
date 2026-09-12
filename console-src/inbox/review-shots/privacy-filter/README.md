# Privacy filter — review shots

Local review: `console-src/inbox/run-review.sh` → `http://127.0.0.1:8766/`

| File | What it shows | URL |
|---|---|---|
| `01-privacy-menu-selected.png` | Filter menu open, **Privacy** selected, list is `requestType === "privacy_request"` only (Lee). Mute Privacy badge. | `/?view=privacy&menu=1` |
| `02-privacy-empty.png` | Empty Privacy view mute copy: `No tickets in this view.` | `/?view=privacy&empty=1&menu=1` |

`?empty=1` pins an empty catalog for review. It is not a product toggle.

Default boot without `?view=` is All (`all`).
Seed `t-lee-privacy` is a privacy request so the filtered list has a row.
First-party `requestType` only. No Shopify Customer Privacy / GDPR write.
