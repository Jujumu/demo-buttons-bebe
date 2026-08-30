"""Minimal MCP stdio server. Tools call the same dispatch as the CLI."""

from __future__ import annotations

import json
import sys
from typing import Any

from .dispatch import invoke, list_tools
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

SCHEMAS = {
    TOOL_LIST_TICKETS: {
        "view": {"type": "string", "description": "open | closed | all | snoozed | mine | unassigned"},
        "limit": {"type": "integer"},
    },
    TOOL_GET_TICKET: {"ticketId": {"type": "string"}},
    TOOL_GET_CUSTOMER: {
        "shop": {"type": "string"},
        "customerId": {"type": "string", "description": "gid://shopify/Customer/…"},
    },
    TOOL_GET_ORDER: {
        "shop": {"type": "string"},
        "orderId": {"type": "string", "description": "gid://shopify/Order/…"},
    },
    TOOL_GET_RETURNS: {
        "shop": {"type": "string"},
        "orderId": {"type": "string", "description": "gid://shopify/Order/…"},
    },
    TOOL_LIST_PAST_ORDERS: {
        "shop": {"type": "string"},
        "customerId": {"type": "string", "description": "gid://shopify/Customer/…"},
    },
    TOOL_DRAFT_REPLY: {
        "ticketId": {"type": "string"},
        "shop": {"type": "string"},
        "thread": {"type": "object", "description": "already-loaded ticket thread"},
        "customer": {"type": "object"},
        "order": {"type": "object"},
        "returns": {"type": "object"},
        "pastOrders": {"type": "array"},
        "customerId": {"type": "string"},
        "orderId": {"type": "string"},
    },
    TOOL_SUMMARIZE_THREAD: {
        "ticketId": {"type": "string"},
        "shop": {"type": "string"},
        "thread": {"type": "object", "description": "already-loaded ticket thread"},
    },
    TOOL_SEARCH_MACROS: {
        "query": {"type": "string", "description": "name, tag, or body substring"},
    },
    TOOL_APPLY_MACRO: {
        "macroId": {"type": "string"},
        "mode": {"type": "string", "description": "replace | append — never a send"},
        "currentBody": {"type": "string", "description": "textarea text to append onto"},
    },
}


def tool_descriptors() -> list[dict[str, Any]]:
    return [
        {
            "name": name,
            "description": f"Helpdesk tissue {name}",
            "inputSchema": {
                "type": "object",
                "properties": SCHEMAS[name],
                "additionalProperties": False,
            },
        }
        for name in list_tools()
    ]


def handle_rpc(message: dict[str, Any]) -> dict[str, Any] | None:
    method = message.get("method")
    rpc_id = message.get("id")
    if method == "notifications/initialized" or rpc_id is None:
        return None
    if method == "initialize":
        result = {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "helpdesk", "version": "1"},
        }
    elif method == "tools/list":
        result = {"tools": tool_descriptors()}
    elif method == "tools/call":
        params = message.get("params") or {}
        payload = invoke(str(params.get("name") or ""), params.get("arguments") or {})
        result = {"content": [{"type": "text", "text": json.dumps(payload)}], "isError": not payload.get("ok")}
    elif method == "ping":
        result = {}
    else:
        return {"jsonrpc": "2.0", "id": rpc_id, "error": {"code": -32601, "message": "method not found"}}
    return {"jsonrpc": "2.0", "id": rpc_id, "result": result}


def run_stdio() -> None:
    for line in sys.stdin:
        text = line.strip()
        if not text:
            continue
        try:
            message = json.loads(text)
        except json.JSONDecodeError:
            continue
        reply = handle_rpc(message)
        if reply is not None:
            sys.stdout.write(json.dumps(reply) + "\n")
            sys.stdout.flush()
