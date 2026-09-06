"""Choose the outbound road for a human Send. No Gorgias imports here."""

from __future__ import annotations

from typing import Any

from .config import gorgias_bridge_enabled, outbound_enabled


def reply_route(ticket: dict[str, Any] | None) -> str:
    """Return 'gorgias', 'email', or 'local'.

    Gorgias only when the switch is ON and the ticket came from Gorgias.
    Otherwise email when outbound is enabled; else local demo append.
    """
    if not outbound_enabled():
        return "local"
    source = str((ticket or {}).get("source") or "").strip().lower()
    if gorgias_bridge_enabled() and source == "gorgias":
        return "gorgias"
    return "email"


def route_label(ticket: dict[str, Any] | None, recipient_email: str | None = None) -> str:
    """Plain-text composer hint. No Gorgias chrome."""
    email = (recipient_email or (ticket or {}).get("fromEmail") or "").strip()
    route = reply_route(ticket)
    if route == "gorgias":
        return f"Sends via Gorgias to {email}" if email else "Sends via Gorgias"
    if route == "email":
        return f"Sends by email to {email}" if email else "Sends by email"
    return "Demo: stays local"
