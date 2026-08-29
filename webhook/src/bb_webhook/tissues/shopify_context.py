"""Module 4 — Shopify Order Context (fixture DTO).

INPUT: ticket id, plus an optional retry flag.
OUTPUT: a support-facing Shopify DTO, an empty state, or an isolated error.
Does not mutate orders. v1 has no Edit / Refund / Cancel actions.
"""

from __future__ import annotations

from .types import Address, OrderLine, PastOrder, Shipment, ShopifyOrder, TissueResult

_SHOPIFY_ERRORS: set[str] = set()
_RETRIED: set[str] = set()

_ORDERS: dict[str, ShopifyOrder] = {
    "tk-1001": ShopifyOrder(
        order_number="1001",
        financial_status="paid",
        fulfillment_status="fulfilled",
        created_label="20 Aug 2026",
        currency="USD",
        subtotal="42.00",
        shipping="5.00",
        tax="3.36",
        total="50.36",
        lines=(
            OrderLine("Cotton Onesie", "BB-ONESIE-NB", 1, "42.00"),
        ),
        addresses=(
            Address("Shipping", "Jane Example", ("100 Example Ave", "Springfield, IL 62701")),
            Address("Billing", "Jane Example", ("100 Example Ave", "Springfield, IL 62701")),
        ),
        shipment=Shipment(
            tracking_number="TRACK1001",
            tracking_url="https://example.com/track/TRACK1001",
            tracking_label="Track shipment",
            carrier="Example Post",
            status="delivered",
        ),
        freshness_label="Fixture · not live Shopify",
    ),
    "tk-1002": ShopifyOrder(
        order_number="1002",
        financial_status="paid",
        fulfillment_status="in transit",
        created_label="27 Aug 2026",
        currency="USD",
        subtotal="36.00",
        shipping="0.00",
        tax="2.88",
        total="38.88",
        lines=(
            OrderLine("Everyday Romper", "BB-ROMPER-3M", 1, "36.00"),
        ),
        addresses=(
            Address("Shipping", "Alex Patron", ("22 Sample Street", "Austin, TX 78701")),
            Address("Billing", "Alex Patron", ("22 Sample Street", "Austin, TX 78701")),
        ),
        shipment=Shipment(
            tracking_number="TRACK1002",
            tracking_url="https://example.com/track/TRACK1002",
            tracking_label="Track shipment",
            carrier="Example Post",
            status="in transit",
        ),
        freshness_label="Fixture · not live Shopify",
    ),
    "tk-1004": ShopifyOrder(
        order_number="1004",
        financial_status="paid",
        fulfillment_status="fulfilled",
        created_label="12 Aug 2026",
        currency="USD",
        subtotal="54.00",
        shipping="5.00",
        tax="4.32",
        total="63.32",
        lines=(
            OrderLine("Knit Set", "BB-KNIT-6M", 1, "54.00"),
        ),
        addresses=(
            Address("Shipping", "Riley Return", ("8 Fixture Lane", "Denver, CO 80202")),
            Address("Billing", "Riley Return", ("8 Fixture Lane", "Denver, CO 80202")),
        ),
        shipment=Shipment(
            tracking_number="TRACK1004",
            tracking_url="https://example.com/track/TRACK1004",
            tracking_label="Track shipment",
            carrier="Example Post",
            status="delivered",
        ),
        freshness_label="Fixture · not live Shopify",
    ),
    "tk-1005": ShopifyOrder(
        order_number="1005",
        financial_status="paid",
        fulfillment_status="fulfilled",
        created_label="01 Aug 2026",
        currency="USD",
        subtotal="28.00",
        shipping="5.00",
        tax="2.24",
        total="35.24",
        lines=(
            OrderLine("Bib Pair", "BB-BIB-2PK", 1, "28.00"),
        ),
        addresses=(
            Address("Shipping", "Casey Closed", ("14 Placeholder Rd", "Portland, OR 97201")),
            Address("Billing", "Casey Closed", ("14 Placeholder Rd", "Portland, OR 97201")),
        ),
        shipment=None,
        freshness_label="Fixture · not live Shopify",
    ),
}

_PAST: dict[str, tuple[PastOrder, ...]] = {
    "tk-1001": (
        PastOrder("0998", "02 Mar 2026", "28.00", "fulfilled"),
        PastOrder("0981", "18 Nov 2025", "44.00", "fulfilled"),
    ),
    "tk-1004": (
        PastOrder("0970", "09 Sep 2025", "36.00", "fulfilled"),
    ),
    "tk-1005": (
        PastOrder("0960", "21 Jun 2025", "22.00", "fulfilled"),
    ),
}

_ERROR_TICKETS = frozenset({"tk-1003"})


def reset_fixtures() -> None:
    _SHOPIFY_ERRORS.clear()
    _SHOPIFY_ERRORS.update(_ERROR_TICKETS)
    _RETRIED.clear()


reset_fixtures()


def health() -> str:
    return "healthy"


def get_order_context(ticket_id: str) -> TissueResult:
    if ticket_id in _SHOPIFY_ERRORS and ticket_id not in _RETRIED:
        return TissueResult(
            status="error",
            error="Shopify context is unavailable.",
        )
    order = _ORDERS.get(ticket_id)
    if order is None:
        return TissueResult(
            status="empty",
            empty_reason="No order is linked. The conversation still works.",
        )
    return TissueResult(status="ok", data=order)


def retry_order_context(ticket_id: str) -> TissueResult:
    """Retry is local to this tissue. Success may still be an empty order."""
    _RETRIED.add(ticket_id)
    return get_order_context(ticket_id)


def get_past_orders(ticket_id: str) -> TissueResult:
    if ticket_id in _SHOPIFY_ERRORS and ticket_id not in _RETRIED:
        return TissueResult(status="error", error="Shopify context is unavailable.")
    past = _PAST.get(ticket_id)
    if not past:
        return TissueResult(status="empty", empty_reason="No past orders.", data={"count": 0, "orders": []})
    return TissueResult(
        status="ok",
        data={"count": len(past), "orders": list(past)},
    )
