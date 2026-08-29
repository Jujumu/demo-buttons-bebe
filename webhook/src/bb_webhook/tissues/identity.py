"""Module 3 — Customer Identity (fixture).

INPUT: ticket id.
OUTPUT: a verified profile, an unidentified empty state, or a tissue error.
Does not fetch Shopify or change ticket status.

Customer keys are Admin GraphQL 2026-07: displayName,
defaultEmailAddress.emailAddress, numberOfOrders, amountSpent.
Never Customer.email.
"""

from __future__ import annotations

from .types import CustomerEmailAddress, CustomerProfile, MoneyV2, TissueResult


def _profile(name: str, email: str, orders: str, spent: str) -> CustomerProfile:
    return CustomerProfile(
        displayName=name,
        defaultEmailAddress=CustomerEmailAddress(emailAddress=email),
        numberOfOrders=orders,
        amountSpent=MoneyV2(amount=spent, currencyCode="USD"),
    )


CUSTOMER_A = _profile("AI-DEMO Customer A", "ai-demo-a@example.com", "1", "28.00")
CUSTOMER_B = _profile("AI-DEMO Customer B", "ai-demo-b@example.com", "1", "32.00")
CUSTOMER_C = _profile("AI-DEMO Customer C", "ai-demo-c@example.com", "1", "48.00")

_PROFILES: dict[str, CustomerProfile] = {
    "tk-1001": CUSTOMER_B,
    "tk-1002": CUSTOMER_A,
    "tk-1003": CUSTOMER_B,
    "tk-1004": CUSTOMER_C,
    "tk-1005": CUSTOMER_A,
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
