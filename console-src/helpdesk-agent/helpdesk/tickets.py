"""First-party ticket tissue. Not Gorgias. Sample threads only.

Ticket status is ours: open / closed / snoozed.
Never Return.status OPEN and never Customer.displayName.
"""

from __future__ import annotations

from .errors import bad_request, not_found
from .fixtures_live_holes import (
    C_FULFILLED,
    C_MULTI,
    C_UNFULFILLED,
    O_1001,
    O_1002,
    O_1003,
)
from .fixtures_sample import ADA, CASEY, JORDAN, ORDER_ADA, ORDER_CASEY_A, ORDER_CASEY_B

VIEWS = ("open", "closed", "all", "snoozed", "mine", "unassigned")
TICKET_STATUSES = ("open", "closed", "snoozed")

ALIASES = {
    "1001": "t-ada-track",
    "1002": "t-casey-visor",
    "1003": "t-jordan-ship",
}

SAMPLE_GIDS = {
    "t-ada-track": (ADA, ORDER_ADA),
    "t-casey-visor": (CASEY, ORDER_CASEY_A),
    "t-casey-throw": (CASEY, ORDER_CASEY_B),
    "t-jordan-ship": (JORDAN, None),
    "t-ada-closed": (ADA, ORDER_ADA),
}

LIVE_GIDS = {
    "t-ada-track": (C_UNFULFILLED, O_1001),
    "t-casey-visor": (C_FULFILLED, O_1002),
    "t-casey-throw": (C_MULTI, O_1003),
    "t-jordan-ship": (C_MULTI, None),
    "t-ada-closed": (C_UNFULFILLED, O_1001),
}

STORE_NAME = "Demo Shop"

TICKETS = (
    {
        "id": "t-ada-track",
        "customerName": "Ada Demo",
        "subject": "Tracking on order #1001 has not moved",
        "snippet": "Where is my order #1001? The tracking has not updated.",
        "status": "open",
        "assignee": "me",
        "updatedAt": "2026-08-28T15:10:00Z",
        "messages": [
            {
                "id": "m1",
                "from": "customer",
                "fromAgent": False,
                "name": "Ada Demo",
                "body": "Where is my order #1001? The tracking has not updated.",
                "at": "2026-08-28T14:02:00Z",
            },
            {
                "id": "m2",
                "from": "agent",
                "fromAgent": True,
                "name": STORE_NAME,
                "body": "Looking at the shipment now — I will write back with the carrier update.",
                "at": "2026-08-28T14:40:00Z",
            },
        ],
        "statusEvents": [
            {"at": "2026-08-28T14:41:00Z", "status": "open", "note": "assigned"},
        ],
    },
    {
        "id": "t-casey-visor",
        "customerName": "Casey Sandbox",
        "subject": "When will order #1002 ship?",
        "snippet": "Please tell me when order #1002 will leave. I need the visor this week.",
        "status": "open",
        "assignee": None,
        "updatedAt": "2026-08-28T16:20:00Z",
        "messages": [
            {
                "id": "m3",
                "from": "customer",
                "fromAgent": False,
                "name": "Casey Sandbox",
                "body": "Please tell me when order #1002 will leave. I need the visor this week.",
                "at": "2026-08-28T16:20:00Z",
            }
        ],
        "statusEvents": [],
    },
    {
        "id": "t-casey-throw",
        "customerName": "Casey Sandbox",
        "subject": "Question about the throw on #1003",
        "snippet": "Did the merino throw on #1003 go out? I want to confirm the shipment.",
        "status": "open",
        "assignee": None,
        "updatedAt": "2026-08-27T11:05:00Z",
        "messages": [
            {
                "id": "m4",
                "from": "customer",
                "fromAgent": False,
                "name": "Casey Sandbox",
                "body": "Did the merino throw on #1003 go out? I want to confirm the shipment.",
                "at": "2026-08-27T11:05:00Z",
            }
        ],
        "statusEvents": [],
    },
    {
        "id": "t-jordan-ship",
        "customerName": "Jordan Preview",
        "subject": "Do you ship the demo catalog to Canada?",
        "snippet": "Do you ship the demo catalog to Canada, or is it local-only?",
        "status": "snoozed",
        "assignee": None,
        "updatedAt": "2026-08-26T09:00:00Z",
        "messages": [
            {
                "id": "m5",
                "from": "customer",
                "fromAgent": False,
                "name": "Jordan Preview",
                "body": "Do you ship the demo catalog to Canada, or is it local-only?",
                "at": "2026-08-26T09:00:00Z",
            }
        ],
        "statusEvents": [
            {"at": "2026-08-26T09:05:00Z", "status": "snoozed", "note": "waiting"},
        ],
    },
    {
        "id": "t-ada-closed",
        "customerName": "Ada Demo",
        "subject": "Received the rattle — thank you",
        "snippet": "The rattle from #1001 arrived. Thank you — you can close this.",
        "status": "closed",
        "assignee": "me",
        "updatedAt": "2026-08-25T18:12:00Z",
        "messages": [
            {
                "id": "m6",
                "from": "customer",
                "fromAgent": False,
                "name": "Ada Demo",
                "body": "The rattle from #1001 arrived. Thank you — you can close this.",
                "at": "2026-08-25T17:50:00Z",
            },
            {
                "id": "m7",
                "from": "agent",
                "fromAgent": True,
                "name": STORE_NAME,
                "body": "Glad it reached you, Ada.",
                "at": "2026-08-25T18:10:00Z",
            },
        ],
        "statusEvents": [
            {"at": "2026-08-25T18:12:00Z", "status": "closed", "note": "answered"},
        ],
    },
)


def _resolve_id(ticket_id: str) -> str:
    return ALIASES.get(str(ticket_id), str(ticket_id))


def _gids_for(ticket_id: str, gid_source: str = "sample") -> tuple[str, str | None]:
    table = LIVE_GIDS if gid_source in {"live", "live-holes"} else SAMPLE_GIDS
    return table.get(ticket_id, (None, None))


def ticket_in_view(ticket: dict, view: str) -> bool:
    status = ticket["status"]
    if view == "all":
        return True
    if view == "open":
        return status == "open"
    if view == "closed":
        return status == "closed"
    if view == "snoozed":
        return status == "snoozed"
    if view == "mine":
        return ticket.get("assignee") == "me" and status == "open"
    if view == "unassigned":
        return ticket.get("assignee") is None and status == "open"
    return False


def _row(ticket: dict, gid_source: str = "sample") -> dict:
    customer_id, order_id = _gids_for(ticket["id"], gid_source)
    return {
        "id": ticket["id"],
        "customerName": ticket["customerName"],
        "subject": ticket["subject"],
        "snippet": ticket["snippet"],
        "status": ticket["status"],
        "updatedAt": ticket["updatedAt"],
        "customerId": customer_id,
        "orderId": order_id,
    }


def list_tickets(view: str = "open", limit: int = 20, gid_source: str = "sample") -> list[dict]:
    if view not in VIEWS:
        raise bad_request("view must be open, closed, all, snoozed, mine, or unassigned", field="view")
    try:
        cap = int(limit)
    except (TypeError, ValueError) as exc:
        raise bad_request("limit must be an integer", field="limit") from exc
    if cap < 1 or cap > 100:
        raise bad_request("limit must be 1..100", field="limit")
    rows = [t for t in TICKETS if ticket_in_view(t, view)]
    return [_row(t, gid_source) for t in rows[:cap]]


def get_ticket(ticket_id: str, gid_source: str = "sample") -> dict:
    if not ticket_id:
        raise bad_request("ticketId is required", field="ticketId")
    canonical = _resolve_id(ticket_id)
    for ticket in TICKETS:
        if ticket["id"] == canonical:
            row = _row(ticket, gid_source)
            row["messages"] = [dict(message) for message in ticket["messages"]]
            row["statusEvents"] = [dict(event) for event in ticket["statusEvents"]]
            return row
    raise not_found("ticket", str(ticket_id))
