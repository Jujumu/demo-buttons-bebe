"""Module 7 — AI draft strip (stub).

INPUT: ticket id, plus insert or discard.
OUTPUT: draft text for the composer, or an empty strip.
Insert copies text into the composer. Discard drops the strip.
This tissue never sends a customer reply.
"""

from __future__ import annotations

from .types import Draft, Macro, TissueResult

_DEFAULT_DRAFTS: dict[str, Draft] = {
    "tk-1001": Draft(
        ticket_id="tk-1001",
        text=(
            "Hi Jane — order 1001 is fulfilled. You can track it with the "
            "shipment link on this ticket. Let me know if it does not update."
        ),
        language="en",
    ),
    "tk-1002": Draft(
        ticket_id="tk-1002",
        text=(
            "Hi Alex — the romper on order 1002 is SKU BB-ROMPER-3M (3 months). "
            "I can help you place a second one if you want the same size."
        ),
        language="en",
    ),
    "tk-1004": Draft(
        ticket_id="tk-1004",
        text=(
            "Hi Riley — your return RET-1004 is in progress with the label created. "
            "The refund is not issued until the parcel is scanned in."
        ),
        language="en",
    ),
}

MACROS: tuple[Macro, ...] = (
    Macro("macro-ship", "shipping times",
          "Domestic orders usually leave within two business days. Tracking appears after fulfillment."),
    Macro("macro-return", "sent return label",
          "Your return label is ready in the returns portal. Refunds start after the parcel is received."),
    Macro("macro-size", "sizing help",
          "If you share the size on the current order I can confirm the matching SKU for a second piece."),
    Macro("macro-care", "care instructions",
          "Wash cold on a gentle cycle and lay flat to dry. Avoid bleach and fabric softener."),
)

_drafts: dict[str, Draft] = {}


def reset_fixtures() -> None:
    global _drafts
    _drafts = dict(_DEFAULT_DRAFTS)


reset_fixtures()


def health() -> str:
    return "healthy"


def get_draft(ticket_id: str) -> TissueResult:
    draft = _drafts.get(ticket_id)
    if draft is None:
        return TissueResult(status="empty", empty_reason="No AI draft for this ticket.")
    return TissueResult(status="ok", data=draft)


def insert_draft(ticket_id: str) -> TissueResult:
    """Return draft text for the composer. Never sends."""
    return get_draft(ticket_id)


def discard_draft(ticket_id: str) -> TissueResult:
    _drafts.pop(ticket_id, None)
    return TissueResult(status="empty", empty_reason="Draft discarded.")


def list_macros() -> tuple[Macro, ...]:
    return MACROS
