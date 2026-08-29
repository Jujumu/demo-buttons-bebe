"""Module 4 — Shopify Order Context (fixture DTO).

INPUT: ticket id, plus an optional retry flag.
OUTPUT: a support-facing Shopify DTO, an empty state, or an isolated error.
Does not mutate orders. v1 has no Edit / Refund / Cancel actions.

Order keys are Admin GraphQL 2026-07. Fixture values follow the
development-store sandbox shape: paid #1002–#1004, null sku, empty
returns, billingAddress often null.
"""

from __future__ import annotations

from .types import (
    EMPTY_RETURNS,
    Fulfillment,
    FulfillmentTrackingInfo,
    LineItemConnection,
    LineItemNode,
    MailingAddress,
    ShopifyOrder,
    TissueResult,
    money_bag,
)

_SHOPIFY_ERRORS: set[str] = set()
_RETRIED: set[str] = set()


def _address(*, name: str, street: str, city_line: str, country: str) -> MailingAddress:
    city, province, zip_code = city_line.split(", ")
    return MailingAddress(
        name=name,
        address1=street,
        address2=None,
        city=city,
        province=province,
        zip=zip_code,
        country=country,
        formatted=(street, city_line, country),
    )


def _line(name: str) -> LineItemConnection:
    return LineItemConnection(nodes=(LineItemNode(name=name, sku=None, quantity=1),))


def _tracking(number: str) -> tuple[Fulfillment, ...]:
    return (
        Fulfillment(
            trackingInfo=(
                FulfillmentTrackingInfo(
                    company="Example Post",
                    number=number,
                    url=f"https://example.com/track/{number}",
                ),
            ),
        ),
    )


_SHIP_A = _address(
    name="AI-DEMO Customer A",
    street="100 Example Ave",
    city_line="Springfield, IL, 62701",
    country="United States",
)
_SHIP_B = _address(
    name="AI-DEMO Customer B",
    street="22 Sample Street",
    city_line="Austin, TX, 78701",
    country="United States",
)
_SHIP_C = _address(
    name="AI-DEMO Customer C",
    street="8 Fixture Lane",
    city_line="Denver, CO, 80202",
    country="United States",
)

ORDER_1002 = ShopifyOrder(
    name="#1002",
    displayFinancialStatus="PAID",
    displayFulfillmentStatus="FULFILLED",
    currentTotalPriceSet=money_bag("28.00"),
    lineItems=_line("Handcrafted Wooden Teether Toy"),
    shippingAddress=_SHIP_A,
    billingAddress=None,
    fulfillments=_tracking("AI-DEMO-1002"),
    returns=EMPTY_RETURNS,
    returnStatus="NO_RETURN",
)
ORDER_1003 = ShopifyOrder(
    name="#1003",
    displayFinancialStatus="PAID",
    displayFulfillmentStatus="UNFULFILLED",
    currentTotalPriceSet=money_bag("32.00"),
    lineItems=_line("Designer Linen Baby Sun Hat"),
    shippingAddress=_SHIP_B,
    billingAddress=None,
    fulfillments=(),
    returns=EMPTY_RETURNS,
    returnStatus="NO_RETURN",
)
ORDER_1004 = ShopifyOrder(
    name="#1004",
    displayFinancialStatus="PAID",
    displayFulfillmentStatus="FULFILLED",
    currentTotalPriceSet=money_bag("48.00"),
    lineItems=_line("Cashmere Knit Baby Blanket"),
    shippingAddress=_SHIP_C,
    billingAddress=_SHIP_C,
    fulfillments=_tracking("AI-DEMO-1004"),
    returns=EMPTY_RETURNS,
    returnStatus="NO_RETURN",
)

_ORDERS: dict[str, ShopifyOrder] = {
    "tk-1001": ORDER_1003,
    "tk-1002": ORDER_1002,
    "tk-1004": ORDER_1004,
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
    if ticket_id not in _ORDERS:
        return TissueResult(
            status="empty",
            empty_reason="No past orders.",
            data={"count": 0, "orders": []},
        )
    return TissueResult(
        status="empty",
        empty_reason="No past orders.",
        data={"count": 0, "orders": []},
    )
