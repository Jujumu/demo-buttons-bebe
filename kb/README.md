# Buttons Bebe knowledge base

This folder contains the local, read-only knowledge base used by the support
agent. Search results help Hermes write a draft for the review console. Hermes
does not send replies or write to Gorgias; a human confirms any customer-facing
action.

## Folders

| Folder | Purpose | Indexed |
|---|---|---|
| `intents/` | Curated intent guidance | Yes |
| `faq/` | Frequently asked questions | Yes |
| `policies/` | Store policy and escalation rules | Yes |
| `tickets/` | Anonymized solved-ticket exemplars | Yes |
| `products/` | Generated Shopify catalog facts | Yes, at `0.85` weight |
| `shopify/` | Shopify platform background | Yes, at `0.70` weight |
| `learned/` | Review holding area for lessons | No |

Store-authored and curated categories use full search weight (`1.0`). The
platform background folder is intentionally lower-weight so store policy wins
when both are plausible matches. The full format and safety rules are in
`CONVENTIONS.md`; search behavior and maintenance are in
`SEARCH-ENGINE.md`.

## Commands

Run these from the `kb/` folder:

```bash
./setup.sh                    # install the local search dependencies once
./update.sh                   # rebuild the validated index after content edits
./search.sh "your question"  # inspect ranked results locally
```

Only local files and the local index are used by search. Do not put credentials,
customer exports, or live service data into this folder.
