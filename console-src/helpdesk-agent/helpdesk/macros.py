"""Composer macro tissue. Search returns bodies; apply fills the box.

Insert/append never send. There is no helpdesk.send. Fixtures work offline
so Ada's inbox does not need Gorgias or a live shop.
"""

from __future__ import annotations

from typing import Any

from .errors import bad_request, not_found

MODES = ("replace", "append")

# Same three fixtures the inbox fallback ships. Titles are the contract field.
MACROS: tuple[dict[str, Any], ...] = (
    {
        "id": "shipping-delay",
        "title": "Shipping delay",
        "tags": ["shipping", "delay"],
        "body": (
            "Hi — this shipment is running behind the usual window. "
            "I am watching the carrier update and will write back when it moves."
        ),
    },
    {
        "id": "return-how-to",
        "title": "Return how-to",
        "tags": ["return", "howto"],
        "body": (
            "You can start a return from the link in your order email. "
            "Pack the unused item, add the label, and drop it with the carrier. "
            "Write back if the link is missing and I will point you to it."
        ),
    },
    {
        "id": "order-status",
        "title": "Order status",
        "tags": ["order", "status", "shipping"],
        "body": (
            "I looked at this order. Once it is paid I can share fulfillment "
            "and tracking from the catalog. Write back if you want the latest carrier note."
        ),
    },
)


def _haystack(macro: dict[str, Any]) -> str:
    tags = " ".join(str(tag) for tag in (macro.get("tags") or []))
    return f"{macro.get('id', '')} {macro.get('title', '')} {tags} {macro.get('body', '')}".lower()


def search_macros(query: str | None = None) -> list[dict[str, Any]]:
    needle = str(query or "").strip().lower()
    rows = [dict(macro) for macro in MACROS]
    if not needle:
        return rows
    return [macro for macro in rows if needle in _haystack(macro)]


def get_macro(macro_id: str) -> dict[str, Any]:
    ident = str(macro_id or "").strip()
    if not ident:
        raise bad_request("macroId is required", field="macroId")
    for macro in MACROS:
        if macro["id"] == ident:
            return dict(macro)
    raise not_found("macro", ident)


def compose_text(body: str, current_body: str = "", mode: str = "replace") -> str:
    chosen = str(mode or "replace").strip().lower()
    if chosen not in MODES:
        raise bad_request("mode must be replace or append", field="mode")
    text = str(body or "")
    current = str(current_body or "")
    if chosen == "append" and current.strip():
        return f"{current.rstrip()}\n\n{text}"
    return text


def handle_search_macros(args: dict[str, Any]) -> dict[str, Any]:
    query = args.get("query")
    if query is None:
        query = args.get("q") or ""
    return {"source": "fixture", "macros": search_macros(str(query))}


def handle_apply_macro(args: dict[str, Any]) -> dict[str, Any]:
    """Return the textarea text. Never a send."""
    macro_id = args.get("macroId") or args.get("macro_id") or args.get("id")
    macro = get_macro(str(macro_id) if macro_id is not None else "")
    current = args.get("currentBody")
    if current is None:
        current = args.get("current_body") or args.get("body") or ""
    mode = str(args.get("mode") or "replace").strip().lower()
    text = compose_text(macro["body"], str(current), mode)
    return {
        "source": "fixture",
        "text": text,
        "title": macro["title"],
        "mode": mode,
        "body": macro["body"],
        "macroId": macro["id"],
    }
