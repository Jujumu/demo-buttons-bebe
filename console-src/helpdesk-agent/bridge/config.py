"""Bridge feature flags. Presence of secrets only — never values."""

from __future__ import annotations

import os
from typing import Any


def _truthy(raw: str | None) -> bool:
    return str(raw or "").strip().lower() in {"1", "true", "yes", "on"}


def _present(name: str) -> bool:
    return bool(os.environ.get(name, "").strip())


def gorgias_bridge_enabled() -> bool:
    return _truthy(os.environ.get("GORGIAS_BRIDGE_ENABLED"))


def outbound_enabled() -> bool:
    return _truthy(os.environ.get("HELPDESK_OUTBOUND_ENABLED"))


def send_allowlist() -> frozenset[str]:
    raw = os.environ.get("HELPDESK_SEND_ALLOWLIST", "").strip()
    if not raw:
        return frozenset()
    return frozenset(part.strip().lower() for part in raw.split(",") if part.strip())


def gorgias_configured() -> bool:
    return all(
        _present(name)
        for name in (
            "GORGIAS_SUBDOMAIN",
            "GORGIAS_API_EMAIL",
            "GORGIAS_API_KEY",
            "GORGIAS_BRIDGE_SECRET",
        )
    )


def email_configured() -> bool:
    return _present("AGENTMAIL_API_KEY")


def bridge_status() -> dict[str, Any]:
    """Read-only status for helpdesk.bridge_status. Never includes secrets."""
    return {
        "gorgiasEnabled": gorgias_bridge_enabled(),
        "gorgiasConfigured": gorgias_configured(),
        "outboundEnabled": outbound_enabled(),
        "emailConfigured": email_configured(),
        "allowlistActive": bool(send_allowlist()),
    }
