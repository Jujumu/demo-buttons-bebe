# Dormant canonical inbox preparation

`GET /console/api/inbox/review-context/gorgias:<ticket-id>` maps through the
existing protected dashboard API to a read-only canonical database snapshot.
It requires the owner session. Required query: `source_message_id`; optional
preconditions: `draft_revision` (SHA256 hex) and `expected_recipient`.
Malformed/noncanonical IDs fail400; unknown source404; a newer customer message,
changed revision, or changed recipient fails409. No provider client is created.

The DTO binds the decimal-string ticket ID, exact source message ID and source
text hash, full draft hash/text, normalized recipient, channel, source timestamp,
and unresolved durable operations. `contextId` hashes that mapping; it is a
change-detection identifier, **not a signature, capability or send authorization**.
Ticket IDs remain strings to avoid JavaScript integer rounding. Source text over
20000characters is explicitly truncated and not reviewable. The context shares
the source lookup SQL used by IntentStore reservation and joins on both ticket
and message ID. It does not create the intents table or write any database row.

`reviewable` means sufficient local data exists for an owner review; it does not
mean a send is permitted. `sendEnabled`, `sendAndCloseEnabled`, and
`providerIdentityVerified` are always false. The message remains exactly
`Activate the send access.` The current inbox UI and static asset manifest do
not load or serve the dormant adapter under `console-src/inbox/dormant/`.
That adapter only performs GET preparation and captures an immutable review
snapshot containing displayed draft and edited review text. It has no send or
close method and exposes no activation flag.

Existing console operations are the only durable action authority. The DTO
surfaces pending/uncertain operation IDs only to their owner; other actors see a
blocking state without an operation identifier. Reopening either console must
resume that existing operation through its status endpoint, not mint another
attempt. Unknown delivery is never cleared by elapsed time or missing messages.
Future posting must use the same IntentStore and GorgiasClient, revalidating the
latest live customer message, recipient, support mailbox and channel before any
external write. A new context request after editing is not permission to replace
the editor's originally reviewed revision. The final approved text must be bound
to the reviewed mapping and confirmation; reviewed text is not automatically an
approved learning example.

Before any future activation, require separate review of the browser action
adapter and server validation, then an explicitly authorized controlled provider
delivery test proving the actual mailbox identity, recipient routing, remote
message ID persistence, terminal delivery observation and interruption recovery.
Model QA alone cannot prove delivery. Send-and-close remains unavailable until a
separate durable close workflow is designed and verified.

The current /inbox and /console share an origin. Cookie stripping protects the
8766 service but does not remove browser authority to the existing console API.
A dedicated inbox origin with host-scoped sessions and narrow same-host action
routing to8000 needs deployment/authentication/Origin proofs before claiming a
separate browser security boundary. Do not introduce credentialed cross-origin
CORS, copy commerce credentials into8766, enable inbox bridge/Shopify mutations,
or repoint any Gorgias webhook as part of this preparation.
