"""Stable tool and CLI names. One tissue each."""

from __future__ import annotations

TOOL_LIST_TICKETS = "helpdesk.list_tickets"
TOOL_GET_TICKET = "helpdesk.get_ticket"
TOOL_GET_CUSTOMER = "helpdesk.get_customer"
TOOL_GET_ORDER = "helpdesk.get_order"
TOOL_GET_RETURNS = "helpdesk.get_returns"
TOOL_LIST_PAST_ORDERS = "helpdesk.list_past_orders"
TOOL_DRAFT_REPLY = "helpdesk.draft_reply"
TOOL_SUMMARIZE_THREAD = "helpdesk.summarize_thread"
TOOL_SEARCH_MACROS = "helpdesk.search_macros"
TOOL_APPLY_MACRO = "helpdesk.apply_macro"
TOOL_INGEST_EMAIL = "helpdesk.ingest_email"
TOOL_INGEST_CHAT = "helpdesk.ingest_chat"

TOOL_NAMES = (
    TOOL_LIST_TICKETS,
    TOOL_GET_TICKET,
    TOOL_GET_CUSTOMER,
    TOOL_GET_ORDER,
    TOOL_GET_RETURNS,
    TOOL_LIST_PAST_ORDERS,
    TOOL_DRAFT_REPLY,
    TOOL_SUMMARIZE_THREAD,
    TOOL_SEARCH_MACROS,
    TOOL_APPLY_MACRO,
    TOOL_INGEST_EMAIL,
    TOOL_INGEST_CHAT,
)

CLI_COMMANDS = {
    TOOL_LIST_TICKETS: "list-tickets",
    TOOL_GET_TICKET: "get-ticket",
    TOOL_GET_CUSTOMER: "get-customer",
    TOOL_GET_ORDER: "get-order",
    TOOL_GET_RETURNS: "get-returns",
    TOOL_LIST_PAST_ORDERS: "list-past-orders",
    TOOL_DRAFT_REPLY: "draft-reply",
    TOOL_SUMMARIZE_THREAD: "summarize-thread",
    TOOL_SEARCH_MACROS: "search-macros",
    TOOL_APPLY_MACRO: "apply-macro",
    TOOL_INGEST_EMAIL: "ingest-email",
    TOOL_INGEST_CHAT: "ingest-chat",
}

SAMPLE_SHOP = "demo-helpdesk.example"
LIVE_HOLE_SHOP = "yznyc1-ez.myshopify.com"
API_VERSION = "2026-07"
