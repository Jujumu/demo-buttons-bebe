"""Clerk DTO lock — Admin GraphQL 2026-07 names only. Not PR 2 guesses."""

from __future__ import annotations

from typing import Any

from .errors import bad_request

BILLING_MISSING_LABEL = "No billing"
TRACKING_MISSING_LABEL = "No tracking"
GIFT_CARDS_MISSING_LABEL = "No gift cards"
DISCOUNTS_MISSING_LABEL = "No discounts"
INVOICE_MISSING_LABEL = "No invoice"


def money_v2(node: dict[str, Any] | None) -> dict[str, str]:
    if not isinstance(node, dict) or "amount" not in node or "currencyCode" not in node:
        raise bad_request("MoneyV2 requires amount and currencyCode")
    return {"amount": str(node["amount"]), "currencyCode": str(node["currencyCode"])}


def money_bag(node: dict[str, Any] | None) -> dict[str, Any]:
    """currentTotalPriceSet is a MoneyBag, not a MoneySet."""
    if not isinstance(node, dict) or "shopMoney" not in node:
        raise bad_request("MoneyBag requires shopMoney")
    out: dict[str, Any] = {"shopMoney": money_v2(node["shopMoney"])}
    presentment = node.get("presentmentMoney")
    if presentment is not None:
        out["presentmentMoney"] = money_v2(presentment)
    return out


def number_of_orders(value: Any) -> str:
    if value is None:
        raise bad_request("numberOfOrders is required")
    return str(value)


def omit_null_sku(line: dict[str, Any]) -> dict[str, Any]:
    out = dict(line)
    if out.get("sku") is None:
        out.pop("sku", None)
    return out


def billing_label(billing_address: Any) -> str:
    if billing_address is None:
        return BILLING_MISSING_LABEL
    return BILLING_MISSING_LABEL if billing_address == {} else "Has billing"


def tracking_label(fulfillments: Any) -> str:
    """Empty fulfillments / no trackingInfo. Does not invent a number."""
    for fulfillment in fulfillments or []:
        if not isinstance(fulfillment, dict):
            continue
        for info in fulfillment.get("trackingInfo") or []:
            if isinstance(info, dict) and (info.get("number") or info.get("url")):
                return "Has tracking"
    return TRACKING_MISSING_LABEL


def line_item(node: dict[str, Any]) -> dict[str, Any]:
    price = node.get("originalUnitPriceSet") or {}
    shop_money = price.get("shopMoney") if isinstance(price, dict) else None
    row: dict[str, Any] = {
        "title": node.get("title"),
        "quantity": node.get("quantity"),
        "originalUnitPriceSet": {"shopMoney": money_v2(shop_money)},
    }
    sku = node.get("sku")
    if sku is not None:
        row["sku"] = sku
    image = node.get("image")
    if isinstance(image, dict) and image.get("url"):
        row["image"] = {"url": str(image["url"])}
        alt = image.get("altText")
        if alt:
            row["image"]["altText"] = str(alt)
    unfulfilled = node.get("unfulfilledQuantity")
    if isinstance(unfulfilled, bool):
        pass
    elif isinstance(unfulfilled, int):
        row["unfulfilledQuantity"] = unfulfilled
    elif isinstance(unfulfilled, str) and unfulfilled.lstrip("-").isdigit():
        row["unfulfilledQuantity"] = int(unfulfilled)
    return omit_null_sku(row)


def clerk_fulfillment(node: dict[str, Any]) -> dict[str, Any]:
    """Official Fulfillment fields only. Do not invent trackingInfo."""
    info = [
        {"number": t.get("number"), "url": t.get("url"), "company": t.get("company")}
        for t in (node.get("trackingInfo") or [])
        if isinstance(t, dict)
    ]
    row: dict[str, Any] = {"trackingInfo": info}
    status = node.get("displayStatus")
    if status:
        row["displayStatus"] = str(status)
    items = node.get("fulfillmentLineItems") or {}
    nodes = items.get("nodes") if isinstance(items, dict) else None
    mapped = []
    for item in nodes or []:
        if not isinstance(item, dict):
            continue
        line = item.get("lineItem") if isinstance(item.get("lineItem"), dict) else {}
        mapped.append(
            {
                "quantity": item.get("quantity"),
                "lineItem": {"title": line.get("title")},
            }
        )
    if mapped:
        row["fulfillmentLineItems"] = {"nodes": mapped}
    return row


def clerk_gift_card(node: dict[str, Any]) -> dict[str, Any]:
    """Official GiftCard fields only. No invented lastFour / status enum."""
    if not isinstance(node, dict) or not node.get("lastCharacters"):
        raise bad_request("GiftCard requires lastCharacters")
    row: dict[str, Any] = {
        "lastCharacters": str(node["lastCharacters"]),
        "enabled": bool(node.get("enabled")),
        "balance": money_v2(node.get("balance")),
    }
    ident = node.get("id")
    if ident:
        row["id"] = str(ident)
    masked = node.get("maskedCode")
    if masked:
        row["maskedCode"] = str(masked)
    return row


def clerk_gift_cards(nodes: Any) -> list[dict[str, Any]]:
    """Fixture GiftCard rows. Live Customer has no giftCards connection — empty."""
    out: list[dict[str, Any]] = []
    for item in nodes or []:
        if isinstance(item, dict):
            out.append(clerk_gift_card(item))
    return out


def clerk_discount_codes(nodes: Any) -> list[str]:
    """Official Order.discountCodes: [String!]."""
    out: list[str] = []
    for item in nodes or []:
        if item is None:
            continue
        text = str(item).strip()
        if text:
            out.append(text)
    return out


def clerk_invoice_url(node: dict[str, Any]) -> str | None:
    """Fixture invoice/receipt URL. Live Order has no official invoiceUrl field."""
    raw = node.get("invoiceUrl")
    if not isinstance(raw, str):
        return None
    url = raw.strip()
    if not url:
        return None
    lower = url.lower()
    if lower.startswith("https://") or lower.startswith("http://"):
        return url
    if url.startswith("/docs/review/"):
        return url
    return None


def clerk_customer(node: dict[str, Any]) -> dict[str, Any]:
    email = node.get("defaultEmailAddress")
    return {
        "id": node["id"],
        "displayName": node.get("displayName"),
        "defaultEmailAddress": (
            {"emailAddress": email["emailAddress"]} if isinstance(email, dict) and email.get("emailAddress") else None
        ),
        "createdAt": node.get("createdAt"),
        "numberOfOrders": number_of_orders(node.get("numberOfOrders")),
        "amountSpent": money_v2(node.get("amountSpent")),
        "tags": list(node.get("tags") or []),
        "giftCards": clerk_gift_cards(node.get("giftCards")),
    }


def clerk_order(node: dict[str, Any]) -> dict[str, Any]:
    lines = node.get("lineItems") or {}
    nodes = lines.get("nodes") if isinstance(lines, dict) else []
    fulfillments = [
        clerk_fulfillment(item)
        for item in (node.get("fulfillments") or [])
        if isinstance(item, dict)
    ]
    return {
        "id": node["id"],
        "name": node.get("name"),
        "createdAt": node.get("createdAt"),
        "displayFinancialStatus": node.get("displayFinancialStatus"),
        "displayFulfillmentStatus": node.get("displayFulfillmentStatus"),
        "currentTotalPriceSet": money_bag(node.get("currentTotalPriceSet")),
        "billingAddress": node.get("billingAddress"),
        "shippingAddress": node.get("shippingAddress"),
        "lineItems": {"nodes": [line_item(item) for item in nodes or []]},
        "fulfillments": fulfillments,
        "discountCodes": clerk_discount_codes(node.get("discountCodes")),
        "invoiceUrl": clerk_invoice_url(node),
    }


def clerk_returns(order: dict[str, Any]) -> dict[str, Any]:
    """Split Return.status from Order.returnStatus. OPEN only drives inProgress."""
    connection = order.get("returns") or {}
    nodes = []
    for item in connection.get("nodes") or []:
        nodes.append(
            {
                "id": item.get("id"),
                "name": item.get("name"),
                "status": item.get("status"),
                "totalQuantity": item.get("totalQuantity"),
            }
        )
    return {
        "orderReturnStatus": order.get("returnStatus") or order.get("orderReturnStatus") or "NO_RETURN",
        "returns": {"nodes": nodes},
        "inProgress": any(item.get("status") == "OPEN" for item in nodes),
    }


def clerk_history_row(node: dict[str, Any]) -> dict[str, Any]:
    bag = money_bag(node.get("currentTotalPriceSet"))
    return {
        "id": node["id"],
        "name": node.get("name"),
        "createdAt": node.get("createdAt"),
        "displayFulfillmentStatus": node.get("displayFulfillmentStatus"),
        "currentTotalPriceSet": {"shopMoney": bag["shopMoney"]},
    }
