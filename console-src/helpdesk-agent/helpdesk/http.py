"""HTTP door. Same invoke() as MCP and CLI. No second GraphQL client."""

from __future__ import annotations

from typing import Any

from .dispatch import invoke
from .names import TOOL_NAMES


def handle_http(tool: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
    return invoke(str(tool or ""), arguments or {})


def allowed_tools() -> tuple[str, ...]:
    return TOOL_NAMES
