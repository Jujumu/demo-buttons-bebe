# Durable human actions and knowledge approval

These changes govern the **existing** support console. The isolated inbox Send
remains hardcoded off. No customer send is performed during verification or
migration; the action table is an additive schema in the existing webhook DB.

The console must deploy with this API version: send and note now require a
canonical UUID `operation_id`, `source_message_id`, exact `draft_revision` SHA256, nonempty text, an authenticated
owner session, trusted Origin, and `confirmed: true`. Internal notes also require
a confirmation dialog. Browser operation IDs survive reloads; localStorage holds
only identifiers, content hashes and outcome state, not reply text.

Before any remote POST, one SQLite transaction captures the source message,
recipient, server draft revision, exact approved text, actor and optional learning
approval. The unique semantic fingerprint prevents two tabs/new keys duplicating
the same source/revision/text. A distinct followup or new source/revision is
allowed once the preceding outcome is known. The Gorgias transport verifies the
latest customer message and recipient still match before posting a public reply.
Missing stored recipients fail closed; use Gorgias for unsupported/missing routing context.
A changed server draft requires a fresh owner review before a new action can reserve.

A repeated operation returns its stored outcome. Reusing its ID for different
actor/text/source/approval is rejected. An unresolved earlier action prevents a
new different reply or note of that kind on the ticket. The returned Gorgias ID
is persisted immediately before delivery polling. `/ticket/{ticket}/actions/{id}`
reconciles that ID using GET only, never by issuing another POST. A provider
acknowledgement is not presented as confirmed delivery.

A network timeout or process crash after remote acceptance but before its ID was
persisted cannot be made exactly-once by this service alone. It remains visibly
unknown and cannot be auto-retried. Inspect the ticket in Gorgias; use the existing
Gorgias operational workflow to resolve it. There is intentionally no API that
blindly clears this uncertainty or retries an unidentifiable message. Keep the
intent row as audit evidence. This is a fail-closed operational limitation, not
a claim of remote exactly-once delivery.

Learning approval is a separate checkbox, default off, captured with the action.
Only an explicitly approved, confirmed-delivered public reply can become an
exemplar. Browser-submitted context and draft metadata are ignored; context comes
from the DB. Notes, generated rewrites, pending sends and legacy packets never
promote automatically. New packets carry reviewer/action/revision hashes, and the
promoter verifies the exact captured situation and final text before masking.
Learning capture failures are logged and retained in the action table for a
safe capture retry through action status; they never cause another send.

Existing historical exemplars may already contain incorrectly approved material.
This change prevents future promotion, but does not silently delete or retroactively
certify that historical corpus. Review/quarantine it separately using its provenance.

Rewrites execute with one concurrent process slot, bounded stdout/stderr, a
150-second limit and complete process-group cleanup on timeout/cancellation.
They require an exact fresh run-token draft block and the same draft cleaner as
the processor. Customer context comes from the stored message. Generated output
never constitutes approval and still requires human factual review. The rewrite
subprocess receives a narrow environment; no Gorgias/Shopify/console secrets are
copied into it. Code dependencies now include the processor's standard-library
draft cleaner, so its updates require a webhook restart as well.
