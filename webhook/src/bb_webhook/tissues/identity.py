"""Module 3 — Customer Identity (fixture).

INPUT: ticket id.
OUTPUT: a verified profile, an unidentified empty state, or a tissue error.
Does not fetch Shopify/Redo or change ticket status.
"""

from __future__ import annotations

from .types import CustomerProfile, TissueResult

_PROFILES: dict[str, CustomerProfile] = {
    "tk-1001": CustomerProfile(
        display_name="Jane Example",
        email="jane.example@example.com",
        phone="+1 555 0101",
        notes="Prefers email. Newborn sizing questions are common.",
        identified=True,
    ),
    "tk-1002": CustomerProfile(
        display_name="Alex Patron",
        email="alex.patron@example.com",
        phone="+1 555 0102",
        notes="Asked about romper sizing on a current order.",
        identified=True,
    ),
    "tk-1003": CustomerProfile(
        display_name="Sam Reviewer",
        email="sam.reviewer@example.com",
        phone=None,
        notes="Care-question ticket. No order is required.",
        identified=True,
    ),
    "tk-1004": CustomerProfile(
        display_name="Riley Return",
        email="riley.return@example.com",
        phone="+1 555 0104",
        notes="Started a portal return for order 1004.",
        identified=True,
    ),
    "tk-1005": CustomerProfile(
        display_name="Casey Closed",
        email="casey.closed@example.com",
        phone="+1 555 0105",
        notes="Delivery confirmed. Ticket is closed.",
        identified=True,
    ),
}


def health() -> str:
    return "healthy"


def get_identity(ticket_id: str) -> TissueResult:
    profile = _PROFILES.get(ticket_id)
    if profile is None:
        return TissueResult(
            status="empty",
            empty_reason="No customer is linked to this ticket.",
        )
    return TissueResult(status="ok", data=profile)
