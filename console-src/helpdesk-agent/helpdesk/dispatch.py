"""Single dispatch used by MCP and CLI."""

from __future__ import annotations

from typing import Any

from .errors import HelpdeskError, bad_request, forbidden_write
from .names import TOOL_NAMES
from .tissues import HANDLERS

TOOLS = TOOL_NAMES

WRITE_TOOLS = frozenset(
    {
        "helpdesk.draft_reply",
        "helpdesk.summarize_thread",
        "helpdesk.send",
        "helpdesk.refund",
        "helpdesk.cancel",
    }
)


def list_tools() -> list[str]:
    return list(TOOL_NAMES)


def dispatch(tool: str, args: dict[str, Any] | None = None) -> dict[str, Any]:
    arguments = dict(args or {})
    if tool in WRITE_TOOLS:
        raise forbidden_write()
    handler = HANDLERS.get(tool)
    if handler is None:
        raise bad_request("unknown tool", tool=tool)
    result = handler(arguments)
    return {"ok": True, "tool": tool, **result}


def invoke(tool: str, args: dict[str, Any] | None = None) -> dict[str, Any]:
    try:
        return dispatch(tool, args)
    except HelpdeskError as exc:
        return exc.as_json()
