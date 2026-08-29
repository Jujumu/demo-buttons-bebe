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
            "Hi — order #1003 is paid and still unfulfilled. The line is the "
            "Designer Linen Baby Sun Hat. There is no SKU on that line."
        ),
        language="en",
    ),
    "tk-1002": Draft(
        ticket_id="tk-1002",
        text=(
            "Hi — order #1002 is paid and fulfilled. Use the Track link on "
            "this ticket. The line has no SKU."
        ),
        language="en",
    ),
    "tk-1004": Draft(
        ticket_id="tk-1004",
        text=(
            "Hi — order #1004 is the Cashmere Knit Baby Blanket. It is paid "
            "and fulfilled. There is no return on this order."
        ),
        language="en",
    ),
}

MACROS: tuple[Macro, ...] = (
    Macro("macro-ship", "shipping times",
          "Domestic orders usually leave within two business days. Tracking appears after fulfillment."),
    Macro("macro-return", "return status",
          "There is no return in progress on this order. I can walk you through starting one in the portal."),
    Macro("macro-size", "sizing help",
          "If you share the size you need I can confirm it against the line on this order."),
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
