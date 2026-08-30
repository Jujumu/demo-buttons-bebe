"""Shopify helpdesk organ: six tissues, one handler path for MCP and CLI."""

from .dispatch import TOOLS, dispatch, list_tools
from .names import CLI_COMMANDS, TOOL_NAMES

__all__ = ["CLI_COMMANDS", "TOOL_NAMES", "TOOLS", "dispatch", "list_tools"]
