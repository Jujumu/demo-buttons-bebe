"""Fail-closed send lock for the production preview organ.

This flag is hardcoded off. Do not read HELPDESK_OUTBOUND_ENABLED here.
Turning send back on is a named human change, not an env flip.
"""

from __future__ import annotations

SEND_ACCESS_ENABLED = False
ACTIVATE_SEND_MESSAGE = "Activate the send access."
SEND_ACCESS_ERROR = "send_access_inactive"


def send_access_enabled() -> bool:
    return False


def refuse_send(*, ticket_id: str | None = None):
    from .errors import HelpdeskError

    details: dict[str, str] = {}
    if ticket_id:
        details["ticketId"] = str(ticket_id)
    raise HelpdeskError(SEND_ACCESS_ERROR, ACTIVATE_SEND_MESSAGE, details=details)
