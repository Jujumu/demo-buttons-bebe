"""Structured failures for MCP and CLI. Never leak stack traces or tokens."""

from __future__ import annotations

from typing import Any


class HelpdeskError(Exception):
    def __init__(self, code: str, message: str, *, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}

    def as_json(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"ok": False, "error": self.code, "message": self.message}
        if self.details:
            payload["details"] = self.details
        return payload


def not_found(kind: str, ident: str) -> HelpdeskError:
    return HelpdeskError("not_found", f"{kind} not found", details={"id": ident})


def bad_request(message: str, **details: Any) -> HelpdeskError:
    return HelpdeskError("bad_request", message, details=details)


def forbidden_write() -> HelpdeskError:
    return HelpdeskError("forbidden", "Shopify writes are refused. SHOPIFY_MUTATIONS_ENABLED stays 0.")
