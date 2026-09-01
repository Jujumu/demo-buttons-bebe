"""Invented sample catalog. Labeled sample. One OPEN return for UI/tests only."""

from __future__ import annotations

from .names import SAMPLE_SHOP

USD = {"amount": "36.00", "currencyCode": "USD"}
BAG = {"shopMoney": USD, "presentmentMoney": USD}
SHIP = {
    "name": "Ada Demo",
    "address1": "1 Sample Wharf",
    "address2": None,
    "city": "Demo City",
    "province": "CA",
    "zip": "90001",
    "country": "US",
}

ADA = "gid://shopify/Customer/9001"
CASEY = "gid://shopify/Customer/9002"
JORDAN = "gid://shopify/Customer/9003"
ORDER_ADA = "gid://shopify/Order/9001"
ORDER_CASEY_A = "gid://shopify/Order/9002"
ORDER_CASEY_B = "gid://shopify/Order/9003"
RETURN_OPEN = "gid://shopify/Return/90011"

CUSTOMERS = {
    ADA: {
        "id": ADA,
        "displayName": "Ada Demo",
        "defaultEmailAddress": {"emailAddress": "ada@demo-helpdesk.example"},
        "createdAt": "2026-04-01T12:00:00Z",
        "numberOfOrders": "1",
        "amountSpent": USD,
        "tags": ["sample"],
    },
    CASEY: {
        "id": CASEY,
        "displayName": "Casey Sandbox",
        "defaultEmailAddress": {"emailAddress": "casey@demo-helpdesk.example"},
        "createdAt": "2026-04-02T12:00:00Z",
        "numberOfOrders": "2",
        "amountSpent": {"amount": "72.00", "currencyCode": "USD"},
        "tags": ["sample"],
    },
    JORDAN: {
        "id": JORDAN,
        "displayName": "Jordan Preview",
        "defaultEmailAddress": None,
        "createdAt": "2026-04-03T12:00:00Z",
        "numberOfOrders": "0",
        "amountSpent": {"amount": "0.00", "currencyCode": "USD"},
        "tags": ["sample"],
    },
}

_LINE = {
    "title": "Sample Romper",
    "sku": None,
    "quantity": 1,
    "originalUnitPriceSet": {"shopMoney": USD},
    "image": {
        "url": "https://images.pexels.com/photos/16222075/pexels-photo-16222075.jpeg?auto=compress&cs=tinysrgb&h=200&w=200&fit=crop",
        "altText": "Sample romper",
    },
}

ORDERS = {
    ORDER_ADA: {
        "id": ORDER_ADA,
        "name": "#9001",
        "createdAt": "2026-05-01T15:00:00Z",
        "displayFinancialStatus": "PAID",
        "displayFulfillmentStatus": "UNFULFILLED",
        "returnStatus": "IN_PROGRESS",
        "currentTotalPriceSet": BAG,
        "billingAddress": None,
        "shippingAddress": SHIP,
        "lineItems": {"nodes": [_LINE]},
        "fulfillments": [],
        "returns": {
            "nodes": [
                {"id": RETURN_OPEN, "name": "#9001-R1", "status": "OPEN", "totalQuantity": 1},
            ]
        },
        "customerId": ADA,
    },
    ORDER_CASEY_A: {
        "id": ORDER_CASEY_A,
        "name": "#9002",
        "createdAt": "2026-05-02T15:00:00Z",
        "displayFinancialStatus": "PAID",
        "displayFulfillmentStatus": "FULFILLED",
        "returnStatus": "NO_RETURN",
        "currentTotalPriceSet": BAG,
        "billingAddress": None,
        "shippingAddress": {**SHIP, "name": "Casey Sandbox"},
        "lineItems": {"nodes": [_LINE]},
        "fulfillments": [
            {
                "trackingInfo": [
                    {
                        "number": "SAMPLE-9002",
                        "url": "https://example.com/sample/9002",
                        "company": "Sample Carrier",
                    }
                ]
            }
        ],
        "returns": {"nodes": []},
        "customerId": CASEY,
    },
    ORDER_CASEY_B: {
        "id": ORDER_CASEY_B,
        "name": "#9003",
        "createdAt": "2026-05-03T15:00:00Z",
        "displayFinancialStatus": "PAID",
        "displayFulfillmentStatus": "UNFULFILLED",
        "returnStatus": "NO_RETURN",
        "currentTotalPriceSet": BAG,
        "billingAddress": None,
        "shippingAddress": {**SHIP, "name": "Casey Sandbox"},
        "lineItems": {"nodes": [_LINE]},
        "fulfillments": [],
        "returns": {"nodes": []},
        "customerId": CASEY,
    },
}

CUSTOMER_ORDERS = {
    ADA: [ORDER_ADA],
    CASEY: [ORDER_CASEY_B, ORDER_CASEY_A],
    JORDAN: [],
}

SHOP = SAMPLE_SHOP
