"""Fixture-backed, read-only Redo MCP service for the Cute Things demo.

This module intentionally has no HTTP client, credentials, or write path.  The
four exported tools mirror ``tools/redo_mcp.py`` and read deterministic local
JSON selected by ``DEMO_REDO_FIXTURES``.
"""

from __future__ import annotations

import copy
import json
import os
from pathlib import Path
from typing import Any, Callable

try:
    from .local_only import require_loopback
except ImportError:  # direct script execution
    from local_only import require_loopback


DEFAULT_FIXTURES = Path(__file__).resolve().parent / "fixtures" / "redo.json"
HOST = require_loopback(
    os.environ.get("REDO_MCP_HOST", "127.0.0.1"),
    "fake Redo MCP",
)
PORT = int(os.environ.get("REDO_MCP_PORT", "8178"))
TRANSPORT = os.environ.get("TRANSPORT", os.environ.get("REDO_MCP_TRANSPORT", "stdio"))

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:  # Tests can import and exercise helpers without MCP installed.
    FastMCP = None  # type: ignore[assignment,misc]


def fixture_path(path: str | os.PathLike[str] | None = None) -> Path:
    """Return the configured fixture path without touching the network."""

    return Path(path or os.environ.get("DEMO_REDO_FIXTURES", DEFAULT_FIXTURES))


def load_fixtures(path: str | os.PathLike[str] | None = None) -> dict[str, Any]:
    """Load and validate the deterministic fixture document."""

    with fixture_path(path).open(encoding="utf-8") as stream:
        data = json.load(stream)
    if not isinstance(data, dict) or not isinstance(data.get("orders"), list) or not isinstance(data.get("returns"), list):
        raise ValueError("Redo fixtures must contain list fields: orders and returns")
    return data


def _clean_order_name(order_name: str) -> str:
    return str(order_name).lstrip("#").strip()


def _trim(ret: Any) -> Any:
    """Expose the stable read-only Redo summary shape used by the live tool."""

    if not isinstance(ret, dict):
        return ret
    aliases = {
        "id": ("id",),
        "status": ("status", "state"),
        "type": ("type",),
        "created_at": ("created_at", "createdAt"),
        "updated_at": ("updated_at", "updatedAt"),
        "complete_with_no_action": ("complete_with_no_action", "completeWithNoAction"),
        "order": ("order",),
        "order_name": ("order_name", "shopify_order_name", "order_number"),
        "external_order_ids": ("external_order_ids", "externalOrderIds"),
        "external_return_ids": ("external_return_ids", "externalReturnIds"),
        "shopify_order_ids": ("shopify_order_ids", "shopifyOrderIds"),
        "compensation_methods": ("compensation_methods", "compensationMethods", "compensation_method"),
        "refunds": ("refunds",),
        "refund_amount": ("refund_amount",),
        "store_credit_amount": ("store_credit_amount",),
        "totals": ("totals", "total"),
        "gift_cards": ("gift_cards", "giftCards"),
        "exchange": ("exchange",),
        "items": ("items", "products", "line_items"),
        "shipments": ("shipments",),
        "dropoffs": ("dropoffs",),
        "tracking": ("tracking",),
        "tracking_url": ("tracking_url", "trackingUrl"),
        "tracking_number": ("tracking_number", "trackingNumber"),
        "notes": ("notes",),
        "tags": ("tags",),
    }
    result: dict[str, Any] = {}
    for canonical, candidates in aliases.items():
        for key in candidates:
            if key in ret:
                result[canonical] = copy.deepcopy(ret[key])
                break
    order = result.get("order")
    if "order_name" not in result and isinstance(order, dict) and order.get("name"):
        result["order_name"] = order["name"]
    return result or copy.deepcopy(ret)


def _error(message: str, **extra: Any) -> dict[str, Any]:
    return {"error": message, **extra}


def _returns() -> list[dict[str, Any]]:
    return load_fixtures()["returns"]


def _orders() -> list[dict[str, Any]]:
    return load_fixtures()["orders"]


def _tool_decorator() -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    if FastMCP is None:
        return lambda function: function
    return mcp.tool()  # type: ignore[name-defined,no-any-return]


if FastMCP is not None:
    mcp = FastMCP("cute-things-demo-redo", host=HOST, port=PORT)


@_tool_decorator()
def list_recent_returns(limit: int = 10) -> dict[str, Any]:
    """List recent fixture returns/RMAs (read-only)."""

    limit = max(0, int(limit))
    returns = [_trim(item) for item in _returns()[:limit]]
    return {"count": len(returns), "returns": returns}


@_tool_decorator()
def get_returns_for_order(order_name: str) -> dict[str, Any]:
    """Look up fixture returns for a Shopify order name or number."""

    clean = _clean_order_name(order_name)
    matches = [item for item in _returns() if _clean_order_name(item.get("order_name", "")) == clean]
    return {"order": order_name, "count": len(matches), "returns": [_trim(item) for item in matches]}


@_tool_decorator()
def get_return(return_id: str) -> dict[str, Any]:
    """Get one fixture return by Redo return id."""

    for item in _returns():
        if str(item.get("id")) == str(return_id):
            return _trim(item)
    return _error("return not found", return_id=return_id)


@_tool_decorator()
def get_order(order_name: str) -> dict[str, Any]:
    """Get full fixture order context, including fulfillment and tracking."""

    clean = _clean_order_name(order_name)
    for item in _orders():
        if _clean_order_name(item.get("name", "")) == clean or str(item.get("id")) == clean:
            return copy.deepcopy(item)
    return _error("order not found", order_name=order_name)


def main() -> None:
    """Run the local MCP server using ``TRANSPORT`` or Redo's env spelling."""

    if FastMCP is None:
        raise RuntimeError("MCP is required to run the fake service; fixture helpers remain importable")
    mcp.run(transport=TRANSPORT)


if __name__ == "__main__":
    main()
