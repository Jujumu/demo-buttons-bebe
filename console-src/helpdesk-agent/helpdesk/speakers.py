"""Inbound From is the customer persona, not the shop/AgentMail login.

`from` on a ticket message stays the role (`customer` / `agent`).
`fromName` / `fromEmail` are the visible speaker. Never Customer.displayName.
"""

from __future__ import annotations

import re
from typing import Any

from .fixtures_intake import MAILBOX_ADDRESS, MAILBOX_DISPLAY

STORE_NAME = "Demo Shop"

_FROM = re.compile(
    r"^\s*(?:(?P<name>.*?)\s*<\s*(?P<email>[^<>\s]+@[^<>\s]+)\s*>|(?P<bare>[^\s@]+@[^\s@]+)|(?P<plain>.+))\s*$"
)

# Shop + roleplay sender inboxes. Display name on those addresses is the persona;
# the address itself is not.
MAILBOX_EMAILS = frozenset(
    {
        MAILBOX_ADDRESS.lower(),
        "teddyjubu@agentmail.to",
    }
)
MAILBOX_NAMES = frozenset(
    {
        MAILBOX_DISPLAY.lower(),
        STORE_NAME.lower(),
        "agentmail",
        "teddyjubu",
        "helpdesk-support",
    }
)


def _clean(value: Any) -> str:
    return str(value or "").strip()


def split_from(value: str) -> tuple[str, str | None]:
    match = _FROM.match(str(value or "").strip())
    if not match:
        return "", None
    email = (match.group("email") or match.group("bare") or "").strip() or None
    name = (match.group("name") or match.group("plain") or "").strip()
    if not name and email:
        name = email
    return name, email.lower() if email else None


def email_local_part(email: str | None) -> str:
    text = _clean(email).lower()
    if "@" not in text:
        return text
    return text.split("@", 1)[0]


def is_mailbox_email(email: str | None) -> bool:
    addr = _clean(email).lower()
    if not addr:
        return False
    if addr in MAILBOX_EMAILS:
        return True
    local = email_local_part(addr)
    return addr.endswith("@agentmail.to") and local in MAILBOX_NAMES


def is_mailbox_name(name: str | None, email: str | None = None) -> bool:
    """True when `name` is missing or is the shop/mailbox login, not a persona."""
    named = _clean(name)
    if not named:
        return True
    lower = named.lower()
    if lower in MAILBOX_NAMES:
        return True
    if is_mailbox_email(named):
        return True
    addr = _clean(email).lower()
    local = email_local_part(addr)
    if is_mailbox_email(email) and (lower == addr or (local and lower == local)):
        return True
    return False


def is_agent_message(message: dict[str, Any] | None) -> bool:
    if not isinstance(message, dict):
        return False
    if message.get("fromAgent") is True:
        return True
    return _clean(message.get("from")).lower() == "agent"


def visible_email(email: str | None) -> str | None:
    addr = _clean(email) or None
    if not addr or is_mailbox_email(addr):
        return None
    return addr


def inbound_from_name(ticket: dict[str, Any], message: dict[str, Any]) -> tuple[str, str | None]:
    from_email = _clean(message.get("fromEmail")) or _clean(ticket.get("fromEmail")) or None
    candidates: list[Any] = [
        message.get("fromName"),
        message.get("name"),
        ticket.get("customerName"),
    ]
    who = message.get("from")
    if isinstance(who, str) and who.lower() not in {"", "customer", "agent"}:
        parsed_name, parsed_email = split_from(who)
        candidates.insert(0, parsed_name)
        from_email = from_email or parsed_email

    from_name = ""
    for candidate in candidates:
        text = _clean(candidate)
        if text and not is_mailbox_name(text, from_email):
            from_name = text
            break
    if not from_name:
        if from_email and not is_mailbox_email(from_email):
            from_name = from_email
        else:
            fallback = _clean(ticket.get("customerName"))
            from_name = fallback if fallback and not is_mailbox_name(fallback, from_email) else "Customer"
    return from_name, from_email or None


def project_customer_name(ticket: dict[str, Any]) -> str:
    name = _clean(ticket.get("customerName"))
    email = _clean(ticket.get("fromEmail")) or None
    if name and not is_mailbox_name(name, email):
        return name
    for message in ticket.get("messages") or []:
        if not isinstance(message, dict) or is_agent_message(message):
            continue
        persona, _ = inbound_from_name(ticket, message)
        if persona and not is_mailbox_name(persona, message.get("fromEmail") or email):
            return persona
    if email and not is_mailbox_email(email):
        return email
    if name and not is_mailbox_name(name, email):
        return name
    return "Customer" if is_mailbox_name(name, email) else (name or "Customer")


def project_message(ticket: dict[str, Any], message: dict[str, Any]) -> dict[str, Any]:
    out = dict(message)
    if is_agent_message(message):
        name = _clean(out.get("fromName") or out.get("name")) or STORE_NAME
        out["from"] = "agent"
        out["fromAgent"] = True
        out["fromName"] = name
        out["name"] = name
        return out
    from_name, from_email = inbound_from_name(ticket, message)
    out["from"] = "customer"
    out["fromAgent"] = False
    out["fromName"] = from_name
    out["name"] = from_name
    if from_email:
        out["fromEmail"] = from_email
    return out
