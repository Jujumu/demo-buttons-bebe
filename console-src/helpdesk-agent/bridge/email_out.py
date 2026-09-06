"""Direct email outbound via AgentMail. Used when Gorgias switch is OFF."""

from __future__ import annotations

import os
from typing import Any


def _attr(obj: Any, *names: str) -> Any:
    for name in names:
        if isinstance(obj, dict) and name in obj:
            return obj[name]
        if hasattr(obj, name):
            return getattr(obj, name)
    return None


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    for name in ("items", "messages", "inboxes", "data"):
        nested = _attr(value, name)
        if isinstance(nested, list):
            return nested
    return list(value) if hasattr(value, "__iter__") and not isinstance(value, (str, bytes, dict)) else []


def _resolve_inbox_id(client: Any, mailbox: str) -> str | None:
    listed = client.inboxes.list(limit=100)
    inboxes = _as_list(_attr(listed, "inboxes", "items") or listed)
    want = mailbox.lower()
    for inbox in inboxes:
        inbox_id = str(_attr(inbox, "inbox_id", "inboxId") or "").strip()
        email = str(_attr(inbox, "email") or "").strip().lower()
        if email == want or inbox_id.lower() == want:
            return inbox_id or mailbox
    return None


def send_email_reply(
    *,
    to_email: str,
    subject: str,
    body: str,
    message_id: str | None = None,
    mailbox: str = "helpdesk-support@agentmail.to",
) -> dict[str, Any]:
    """Reply in-thread when message_id is known; otherwise send a fresh Re: email."""
    from helpdesk.send_access import ACTIVATE_SEND_MESSAGE, send_access_enabled

    if not send_access_enabled():
        return {"ok": False, "error": ACTIVATE_SEND_MESSAGE}
    if not os.environ.get("AGENTMAIL_API_KEY", "").strip():
        return {"ok": False, "error": "AGENTMAIL_API_KEY is not set"}
    text = str(body or "").strip()
    recipient = str(to_email or "").strip()
    if not text or not recipient:
        return {"ok": False, "error": "recipient and text are required"}
    try:
        from agentmail import AgentMail
    except ImportError as exc:
        return {"ok": False, "error": f"agentmail package missing: {exc}"}
    client = AgentMail()
    inbox_id = _resolve_inbox_id(client, mailbox)
    if not inbox_id:
        return {"ok": False, "error": f"mailbox not found: {mailbox}"}
    try:
        if message_id:
            sent = client.inboxes.messages.reply(
                inbox_id=inbox_id,
                message_id=str(message_id),
                text=text,
            )
        else:
            re_subject = subject if str(subject).lower().startswith("re:") else f"Re: {subject}"
            sent = client.inboxes.messages.send(
                inbox_id=inbox_id,
                to=recipient,
                subject=re_subject,
                text=text,
            )
    except Exception as exc:  # noqa: BLE001 — surface as structured failure
        return {"ok": False, "error": str(exc)[:400]}
    mid = _attr(sent, "message_id", "messageId", "id")
    return {
        "ok": True,
        "messageId": str(mid) if mid else None,
        "deliveryStatus": "sent",
        "via": "email",
    }
