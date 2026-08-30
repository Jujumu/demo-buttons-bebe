"""Offline mirror of Cute Things live holes. Empty returns. No OPEN invented."""

from __future__ import annotations

from .names import LIVE_HOLE_SHOP

C_UNFULFILLED = "gid://shopify/Customer/10207427887277"
C_FULFILLED = "gid://shopify/Customer/10207427920045"
C_MULTI = "gid://shopify/Customer/10207427952813"
O_1001 = "gid://shopify/Order/7131035795629"
O_1002 = "gid://shopify/Order/7131035861165"
O_1003 = "gid://shopify/Order/7131035893933"
O_1004 = "gid://shopify/Order/7131035992237"

USD = {"amount": "28.00", "currencyCode": "USD"}
BAG = {"shopMoney": USD, "presentmentMoney": USD}
SHIP = {
    "name": "Demo Unfulfilled",
    "address1": "10 Hole Street",
    "address2": None,
    "city": "Sandbox",
    "province": "NY",
    "zip": "10001",
    "country": "US",
}
LINE = {
    "title": "Organic Cotton Baby Romper",
    "sku": None,
    "quantity": 1,
    "originalUnitPriceSet": {"shopMoney": USD},
}
EMPTY_RETURNS = {"nodes": []}


def _customer(gid: str, name: str, orders: str, spent: str) -> dict:
    return {
        "id": gid,
        "displayName": name,
        "defaultEmailAddress": None,
        "createdAt": "2026-08-01T12:00:00Z",
        "numberOfOrders": orders,
        "amountSpent": {"amount": spent, "currencyCode": "USD"},
        "tags": ["sample"],
    }


def _order(gid: str, name: str, created: str, fulfill: str, customer_id: str, tracking=None, title=None):
    line = dict(LINE)
    if title:
        line["title"] = title
    return {
        "id": gid,
        "name": name,
        "createdAt": created,
        "displayFinancialStatus": "PAID",
        "displayFulfillmentStatus": fulfill,
        "returnStatus": "NO_RETURN",
        "currentTotalPriceSet": BAG,
        "billingAddress": None,
        "shippingAddress": {**SHIP, "name": name.replace("#", "Order ")},
        "lineItems": {"nodes": [line]},
        "fulfillments": [{"trackingInfo": [tracking]}] if tracking else [],
        "returns": EMPTY_RETURNS,
        "customerId": customer_id,
    }


CUSTOMERS = {
    C_UNFULFILLED: _customer(C_UNFULFILLED, "Demo Unfulfilled", "1", "28.00"),
    C_FULFILLED: _customer(C_FULFILLED, "Demo Fulfilled", "1", "28.00"),
    C_MULTI: _customer(C_MULTI, "Demo Multiple Orders", "2", "56.00"),
}

ORDERS = {
    O_1001: _order(O_1001, "#1001", "2026-08-10T14:00:00Z", "UNFULFILLED", C_UNFULFILLED),
    O_1002: _order(
        O_1002,
        "#1002",
        "2026-08-10T14:10:00Z",
        "FULFILLED",
        C_FULFILLED,
        tracking={
            "number": "AI-DEMO-1002",
            "url": "https://example.com/ai-demo/1002",
            "company": "Demo Carrier",
        },
        title="Handcrafted Wooden Teether Toy",
    ),
    O_1003: _order(
        O_1003, "#1003", "2026-08-10T14:20:00Z", "UNFULFILLED", C_MULTI, title="Designer Linen Baby Sun Hat"
    ),
    O_1004: _order(
        O_1004,
        "#1004",
        "2026-08-10T14:30:00Z",
        "FULFILLED",
        C_MULTI,
        tracking={
            "number": "AI-DEMO-1004",
            "url": "https://example.com/ai-demo/1004",
            "company": "Demo Carrier",
        },
        title="Cashmere Knit Baby Blanket",
    ),
}

CUSTOMER_ORDERS = {
    C_UNFULFILLED: [O_1001],
    C_FULFILLED: [O_1002],
    C_MULTI: [O_1004, O_1003],
}

SHOP = LIVE_HOLE_SHOP
