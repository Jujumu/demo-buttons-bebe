"""Compatibility shim for the package-backed Hermes runner."""

from hermes_runner import (  # noqa: F401
    build_hermes_command,
    draft_for_console,
    process_ticket_with_hermes,
)

__all__ = [
    "build_hermes_command",
    "draft_for_console",
    "process_ticket_with_hermes",
]
