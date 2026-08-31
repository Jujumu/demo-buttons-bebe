"""Caduceus composer tissue. Text out only — never a send.

Input is a ticket thread plus optional rail DTOs (or the six read tools).
Output is a merchant-reply draft or a mute thread peek. No Shopify writes.
processor/draft_generator.py is a retired processor stub that mentions Gorgias
threads; this organ does not import it.
"""

from __future__ import annotations

from typing import Any

from . import tickets
from .errors import HelpdeskError, bad_request
from .fixtures_sample import ADA, CASEY, JORDAN, ORDER_ADA, ORDER_CASEY_A
from .names import SAMPLE_SHOP
from .shop import rail_get_customer, rail_get_order, rail_get_returns, rail_list_past_orders

# Sample ticket → rail GIDs so CLI `draft-reply --ticket 1001` can load context.
SAMPLE_RAIL = {
    "1001": {"customerId": ADA, "orderId": ORDER_ADA},
    "1002": {"customerId": CASEY, "orderId": ORDER_CASEY_A},
    "1003": {"customerId": JORDAN, "orderId": None},
}

def _ticket_id(args: dict[str, Any]) -> str:
    value = args.get("ticketId") or args.get("ticket") or args.get("ticket_id")
    return str(value).strip() if value is not None else ""


def _as_record(value: Any) -> dict[str, Any] | None:
    return value if isinstance(value, dict) else None


def _as_list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _talk_messages(thread: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for message in thread.get("messages") or []:
        if not isinstance(message, dict):
            continue
        if message.get("kind") == "status":
            continue
        rows.append(message)
    return rows


def _from_customer(message: dict[str, Any]) -> bool:
    if message.get("fromAgent") is True:
        return False
    who = str(message.get("from") or "").strip().lower()
    return who in {"", "customer"}


def _customer_name(thread: dict[str, Any], _customer: dict[str, Any] | None) -> str:
    """Ticket customerName / message name only. Never Customer.displayName."""
    if thread.get("customerName"):
        return str(thread["customerName"])
    for message in _talk_messages(thread):
        if _from_customer(message) and message.get("name"):
            return str(message["name"])
    return ""


def _first_name(full: str) -> str:
    token = (full or "").strip().split()
    return token[0] if token else "there"


def _tracking(order: dict[str, Any] | None) -> tuple[str, str]:
    if not order:
        return "", ""
    for fulfillment in order.get("fulfillments") or []:
        if not isinstance(fulfillment, dict):
            continue
        for info in fulfillment.get("trackingInfo") or []:
            if not isinstance(info, dict):
                continue
            number = str(info.get("number") or "").strip()
            company = str(info.get("company") or "").strip()
            if number:
                return company, number
    return "", ""


def _open_return(returns: dict[str, Any] | None) -> bool:
    if not returns:
        return False
    if returns.get("inProgress") is True:
        return True
    for node in (returns.get("returns") or {}).get("nodes") or []:
        if isinstance(node, dict) and str(node.get("status") or "") == "OPEN":
            return True
    return False


def _last_customer_body(thread: dict[str, Any]) -> str:
    for message in reversed(_talk_messages(thread)):
        if _from_customer(message) and message.get("body"):
            return str(message["body"]).strip()
    return str(thread.get("snippet") or thread.get("subject") or "").strip()


def _customer_photo_count(thread: dict[str, Any]) -> int:
    total = 0
    for message in _talk_messages(thread):
        if not _from_customer(message):
            continue
        attachments = message.get("attachments") or []
        if isinstance(attachments, list):
            total += sum(1 for item in attachments if isinstance(item, dict) and item.get("url"))
    return total


def _load_thread(args: dict[str, Any]) -> dict[str, Any]:
    thread = _as_record(args.get("thread"))
    if thread and (thread.get("messages") is not None or thread.get("subject") or thread.get("id")):
        loaded = dict(thread)
        if not loaded.get("id"):
            loaded["id"] = _ticket_id(args)
        return loaded
    ticket_id = _ticket_id(args)
    if not ticket_id:
        raise bad_request("ticketId is required", field="ticketId")
    return tickets.get_ticket(ticket_id)


def _lookup_ids(args: dict[str, Any], thread: dict[str, Any]) -> tuple[str | None, str | None]:
    mapped = SAMPLE_RAIL.get(str(thread.get("id") or _ticket_id(args)))
    customer_id = args.get("customerId") or args.get("customer_id") or thread.get("customerId")
    order_id = args.get("orderId") or args.get("order_id") or thread.get("orderId")
    if mapped:
        customer_id = customer_id or mapped.get("customerId")
        order_id = order_id if order_id is not None else mapped.get("orderId")
    return (
        str(customer_id) if customer_id else None,
        str(order_id) if order_id else None,
    )


def _try_rail(loader, shop: str | None, ident: str | None) -> Any | None:
    if not shop or not ident:
        return None
    try:
        _source, payload = loader(shop, ident)
        return payload
    except HelpdeskError:
        return None


def _load_rail(args: dict[str, Any], thread: dict[str, Any]) -> dict[str, Any]:
    shop = args.get("shop") or (SAMPLE_SHOP if str(thread.get("id") or "") in SAMPLE_RAIL else None)
    customer = _as_record(args.get("customer"))
    order = _as_record(args.get("order"))
    returns = _as_record(args.get("returns"))
    past_orders = args.get("pastOrders") if args.get("pastOrders") is not None else args.get("past_orders")
    customer_id, order_id = _lookup_ids(args, thread)
    if customer is None:
        customer = _try_rail(rail_get_customer, shop, customer_id)
    if order is None:
        order = _try_rail(rail_get_order, shop, order_id)
    if returns is None:
        returns = _try_rail(rail_get_returns, shop, order_id)
    if not isinstance(past_orders, list):
        past_orders = _try_rail(rail_list_past_orders, shop, customer_id) or []
    return {
        "customer": customer,
        "order": order,
        "returns": returns,
        "pastOrders": _as_list(past_orders),
    }


def fixture_draft(thread: dict[str, Any], rail: dict[str, Any]) -> str:
    """Merchant-reply draft. Never promises a refund, cancel, or send."""
    customer = rail.get("customer")
    order = rail.get("order")
    returns = rail.get("returns")
    name = _first_name(_customer_name(thread, customer if isinstance(customer, dict) else None))
    status = str(thread.get("status") or "").lower()
    order_rec = order if isinstance(order, dict) else None
    order_name = str((order_rec or {}).get("name") or "").strip()
    financial = str((order_rec or {}).get("displayFinancialStatus") or "").replace("_", " ").title()
    fulfill = str((order_rec or {}).get("displayFulfillmentStatus") or "").replace("_", " ").title()
    company, tracking = _tracking(order_rec)
    open_return = _open_return(returns if isinstance(returns, dict) else None)
    asked = _last_customer_body(thread)

    sentences: list[str] = []
    if status == "closed":
        sentences.append(f"Glad this reached you, {name}.")
        if order_name:
            sentences.append(f"{order_name} can stay closed — write back if anything else comes up.")
        else:
            sentences.append("I am here if anything else comes up.")
        return " ".join(sentences)

    greet = f"Hi {name} —"
    if order_name and financial and fulfill:
        sentences.append(f"{greet} I looked at {order_name}. It is {financial} and {fulfill}.")
    elif order_name:
        sentences.append(f"{greet} I looked at {order_name}.")
    else:
        sentences.append(f"{greet} I can confirm the destination once an order is on this ticket.")

    if tracking:
        label = f"{company} {tracking}".strip() if company else tracking
        sentences.append(f"The carrier update is {label}.")
    elif order_name and fulfill.lower() == "unfulfilled":
        sentences.append("It has not been handed to a carrier yet. I will write back when it ships.")

    if open_return:
        sentences.append("There is an open return on this order. I will not refund or cancel from here.")

    photos = _customer_photo_count(thread)
    if photos == 1:
        sentences.append("I can see the photo you attached and will use it while we sort this out.")
    elif photos > 1:
        sentences.append(f"I can see the {photos} photos you attached and will use them while we sort this out.")

    if asked and not order_name:
        sentences.append("Happy to answer from the published catalog once we have an order to check.")

    sentences.append("Let me know if you need anything else.")
    return " ".join(sentences)


def fixture_summary(thread: dict[str, Any]) -> str:
    """Short mute peek of the thread. Not a reply and never a send."""
    name = _customer_name(thread, None) or "Customer"
    subject = str(thread.get("subject") or "").strip()
    asked = _last_customer_body(thread)
    count = len(_talk_messages(thread))
    status = str(thread.get("status") or "open")
    screen = "Open" if status == "open" else status.replace("_", " ").title()
    who = name.split()[0] if name else "Customer"
    if asked and subject:
        lead = f"{who} asked: {asked}"
        if asked.rstrip().endswith("?"):
            lead = f"{who} asked {asked[0].lower() + asked[1:]}" if asked else lead
        return f"{lead} Subject: {subject}. {count} message{'s' if count != 1 else ''}. Ticket is {screen}."
    if asked:
        return f"{who} asked: {asked} {count} message{'s' if count != 1 else ''}. Ticket is {screen}."
    return f"{who} wrote in. {count} message{'s' if count != 1 else ''}. Ticket is {screen}."


def handle_draft_reply(args: dict[str, Any]) -> dict[str, Any]:
    thread = _load_thread(args)
    rail = _load_rail(args, thread)
    return {"source": "fixture", "draft": fixture_draft(thread, rail)}


def handle_summarize_thread(args: dict[str, Any]) -> dict[str, Any]:
    thread = _load_thread(args)
    return {"source": "fixture", "summary": fixture_summary(thread)}
