"""First-party ticket tissue. Not Gorgias. Sample threads only."""

from __future__ import annotations

from .errors import bad_request, not_found

VIEWS = ("open", "closed", "all")

TICKETS = (
    {
        "id": "1001",
        "customerName": "Ada Demo",
        "subject": "Where is my sample order?",
        "snippet": "Has #9001 left the warehouse yet?",
        "status": "open",
        "updatedAt": "2026-05-04T10:00:00Z",
        "messages": [
            {
                "id": "m-1001-1",
                "from": "customer",
                "body": "Has #9001 left the warehouse yet?",
                "at": "2026-05-04T09:50:00Z",
            }
        ],
        "statusEvents": [
            {"at": "2026-05-04T09:50:00Z", "status": "open", "note": "created"},
        ],
    },
    {
        "id": "1002",
        "customerName": "Casey Sandbox",
        "subject": "Tracking for the fulfilled sample",
        "snippet": "Need the carrier link for #9002.",
        "status": "open",
        "updatedAt": "2026-05-04T11:00:00Z",
        "messages": [
            {
                "id": "m-1002-1",
                "from": "customer",
                "body": "Need the carrier link for #9002.",
                "at": "2026-05-04T10:40:00Z",
            }
        ],
        "statusEvents": [
            {"at": "2026-05-04T10:40:00Z", "status": "open", "note": "created"},
        ],
    },
    {
        "id": "1003",
        "customerName": "Jordan Preview",
        "subject": "Sizing before I order",
        "snippet": "Do sample rompers run large?",
        "status": "closed",
        "updatedAt": "2026-05-01T16:00:00Z",
        "messages": [
            {
                "id": "m-1003-1",
                "from": "customer",
                "body": "Do sample rompers run large?",
                "at": "2026-05-01T15:00:00Z",
            }
        ],
        "statusEvents": [
            {"at": "2026-05-01T15:00:00Z", "status": "open", "note": "created"},
            {"at": "2026-05-01T16:00:00Z", "status": "closed", "note": "answered"},
        ],
    },
)


def list_tickets(view: str = "open", limit: int = 20) -> list[dict]:
    if view not in VIEWS:
        raise bad_request("view must be open, closed, or all", field="view")
    try:
        cap = int(limit)
    except (TypeError, ValueError) as exc:
        raise bad_request("limit must be an integer", field="limit") from exc
    if cap < 1 or cap > 100:
        raise bad_request("limit must be 1..100", field="limit")
    rows = [t for t in TICKETS if view == "all" or t["status"] == view]
    return [
        {
            "id": t["id"],
            "customerName": t["customerName"],
            "subject": t["subject"],
            "snippet": t["snippet"],
            "status": t["status"],
            "updatedAt": t["updatedAt"],
        }
        for t in rows[:cap]
    ]


def get_ticket(ticket_id: str) -> dict:
    if not ticket_id:
        raise bad_request("ticketId is required", field="ticketId")
    for ticket in TICKETS:
        if ticket["id"] == str(ticket_id):
            return {
                "id": ticket["id"],
                "customerName": ticket["customerName"],
                "subject": ticket["subject"],
                "snippet": ticket["snippet"],
                "status": ticket["status"],
                "updatedAt": ticket["updatedAt"],
                "messages": list(ticket["messages"]),
                "statusEvents": list(ticket["statusEvents"]),
            }
    raise not_found("ticket", str(ticket_id))
