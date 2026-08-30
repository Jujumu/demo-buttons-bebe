"""Invoke the helpdesk organ from the webhook process. Same handlers as MCP/CLI."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any


def helpdesk_root() -> Path:
    return Path(__file__).resolve().parents[3] / "console-src" / "helpdesk-agent"


def _ensure_path() -> None:
    root = str(helpdesk_root())
    if root not in sys.path:
        sys.path.insert(0, root)


def handle_tool(tool: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
    _ensure_path()
    from helpdesk.http import handle_http

    return handle_http(tool, arguments)
