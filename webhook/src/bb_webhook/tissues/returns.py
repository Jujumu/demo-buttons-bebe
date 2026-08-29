"""Fixture returns tissue for the inbox rail.

INPUT: ticket id.
OUTPUT: an in-progress return, or an empty degrade.
Not a live Redo integration. No network calls.
"""

from __future__ import annotations

from .types import ReturnRecord, TissueResult

_RETURNS: dict[str, ReturnRecord] = {
    "tk-1004": ReturnRecord(
        return_id="RET-1004",
        in_progress=True,
        stage="Label created",
        next_step="Customer has the return label and can drop the parcel off.",
        refund_status="Not yet refunded",
        freshness_label="Fixture · not a live returns provider",
    ),
}


def health() -> str:
    return "healthy"


def get_return_context(ticket_id: str) -> TissueResult:
    record = _RETURNS.get(ticket_id)
    if record is None:
        return TissueResult(
            status="empty",
            empty_reason="No return in progress.",
        )
    return TissueResult(status="ok", data=record)
