"""Shopify helpdesk organ: eight tissues, one handler path for MCP, CLI, and HTTP."""

from .dispatch import TOOLS, dispatch, list_tools
from .names import CLI_COMMANDS, TOOL_NAMES

__all__ = ["CLI_COMMANDS", "TOOL_NAMES", "TOOLS", "dispatch", "list_tools"]
