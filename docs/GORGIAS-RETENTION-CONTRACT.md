# Gorgias retained message reads

The September 8, 2026 retention change makes old email full bodies and headers nullable when stripped content exists. Webhook normalization and the five-tool read-only MCP now prefer stripped text/HTML, then full bodies. Webhook HTML is converted to visible plain text; MCP retains original metadata and adds explicit preferred-content/unavailable hints. Neither fetches `body_url`. The retired feedback poller is not reactivated.

Message pages use the documented `GET /messages` with `ticket_id`, a bounded limit, explicit newest-first order, and an optional opaque cursor. Response pagination metadata remains intact. A single page must not be described as complete history. The old ticket-specific message endpoint is deprecated and does not document the limit argument previously sent to it.

Provider sent timestamps accept valid ISO datetime values with or without timezone offsets, including the naive form in Gorgias examples. Date-only values and malformed receipts never establish delivery. A provider sent timestamp is provider evidence, not proof of recipient inbox arrival.

Official contracts:
- https://developers.gorgias.com/changelog/new-email-message-data-retention-policy
- https://developers.gorgias.com/reference/the-ticketmessage-object
- https://developers.gorgias.com/reference/list-messages
- https://developers.gorgias.com/reference/list-ticket-messages
- https://developers.gorgias.com/reference/pagination

All changes are read-only. Inbox Send remains locked. Tests use synthetic payloads and mocked requests only.
