"""Ten tissue handlers. Input → output only."""

from __future__ import annotations

from typing import Any

from . import tickets
from .composer import handle_draft_reply, handle_summarize_thread
from .macros import handle_apply_macro, handle_search_macros
from .names import (
    TOOL_APPLY_MACRO,
    TOOL_DRAFT_REPLY,
    TOOL_GET_CUSTOMER,
    TOOL_GET_ORDER,
    TOOL_GET_RETURNS,
    TOOL_GET_TICKET,
    TOOL_LIST_PAST_ORDERS,
    TOOL_LIST_TICKETS,
    TOOL_SEARCH_MACROS,
    TOOL_SUMMARIZE_THREAD,
)
from .shop import rail_get_customer, rail_get_order, rail_get_returns, rail_list_past_orders


def handle_list_tickets(args: dict[str, Any]) -> dict[str, Any]:
    view = str(args.get("view") or "open")
    limit = args.get("limit", 20)
    return {"source": "sample", "tickets": tickets.list_tickets(view, limit)}


def handle_get_ticket(args: dict[str, Any]) -> dict[str, Any]:
    ticket_id = args.get("ticketId") or args.get("ticket_id")
    return {"source": "sample", "ticket": tickets.get_ticket(str(ticket_id) if ticket_id is not None else "")}


def handle_get_customer(args: dict[str, Any]) -> dict[str, Any]:
    source, customer = rail_get_customer(args.get("shop"), args.get("customerId") or args.get("customer_id"))
    return {"source": source, "customer": customer}


def handle_get_order(args: dict[str, Any]) -> dict[str, Any]:
    source, order = rail_get_order(args.get("shop"), args.get("orderId") or args.get("order_id"))
    return {"source": source, "order": order}


def handle_get_returns(args: dict[str, Any]) -> dict[str, Any]:
    source, payload = rail_get_returns(args.get("shop"), args.get("orderId") or args.get("order_id"))
    return {"source": source, **payload}


def handle_list_past_orders(args: dict[str, Any]) -> dict[str, Any]:
    source, orders = rail_list_past_orders(args.get("shop"), args.get("customerId") or args.get("customer_id"))
    return {"source": source, "orders": orders}


HANDLERS = {
    TOOL_LIST_TICKETS: handle_list_tickets,
    TOOL_GET_TICKET: handle_get_ticket,
    TOOL_GET_CUSTOMER: handle_get_customer,
    TOOL_GET_ORDER: handle_get_order,
    TOOL_GET_RETURNS: handle_get_returns,
    TOOL_LIST_PAST_ORDERS: handle_list_past_orders,
    TOOL_DRAFT_REPLY: handle_draft_reply,
    TOOL_SUMMARIZE_THREAD: handle_summarize_thread,
    TOOL_SEARCH_MACROS: handle_search_macros,
    TOOL_APPLY_MACRO: handle_apply_macro,
}
