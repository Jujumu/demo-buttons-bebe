"""First-party ticket tissue. Not Gorgias. Sample threads plus intake.

Ticket status is ours: open / closed / snoozed.
Never Return.status OPEN and never Customer.displayName.
Spam never becomes a ticket and never appears in list_tickets.
"""

from __future__ import annotations

import copy
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from .errors import bad_request, not_found
from .speakers import project_customer_name, project_message
from .fixtures_live_holes import (
    C_FULFILLED,
    C_MULTI,
    C_UNFULFILLED,
    O_1001,
    O_1002,
    O_1003,
)
from .fixtures_demo_tickets import DEMO_SEED_TICKETS
from .fixtures_sample import ADA, CASEY, JORDAN, ORDER_ADA, ORDER_CASEY_A, ORDER_CASEY_B

VIEWS = ("open", "closed", "all", "snoozed", "mine", "unassigned")
TICKET_STATUSES = ("open", "closed", "snoozed")
REQUEST_TYPES = ("marketing_unsubscribe", "privacy_request", "bug")
PRIVACY_SUBTYPES = ("access", "delete", "export")
SEVERITIES = ("low", "medium", "high", "critical")
_BUG_TYPE_RE = re.compile(r"\b(?:bug|crash(?:es|ed|ing)?)\b", re.I)
_BROKEN_RE = re.compile(r"\bbroken\b", re.I)
_TECH_RE = re.compile(r"\b(?:ios|iphone|ipad|android|app|device)\b", re.I)
_IOS_RE = re.compile(r"\b(?:ios|iphone|ipad)\b", re.I)
_ANDROID_RE = re.compile(r"\bandroid\b", re.I)
_CRITICAL_RE = re.compile(r"\bcritical\b", re.I)
_CRASH_RE = re.compile(r"\bcrash(?:es|ed|ing)?\b", re.I)
_LOW_RE = re.compile(r"\b(?:low|minor)\b", re.I)
_PRIVACY_MARKERS = (
    "privacy",
    "gdpr",
    "delete my data",
    "data request",
    "privacy request",
    "delete my personal data",
    "data deletion",
    "data export",
    "export my data",
    "right to be forgotten",
    "erase my data",
)

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

SEED_TICKETS = (
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
                "fromName": "Ada Demo",
                "body": "Where is my order #1001? The tracking has not updated.",
                "at": "2026-08-28T14:02:00Z",
            },
            {
                "id": "m2",
                "from": "agent",
                "fromAgent": True,
                "name": STORE_NAME,
                "fromName": STORE_NAME,
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
                "fromName": "Casey Sandbox",
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
                "fromName": "Casey Sandbox",
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
                "fromName": "Jordan Preview",
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
                "fromName": "Ada Demo",
                "body": "The rattle from #1001 arrived. Thank you — you can close this.",
                "at": "2026-08-25T17:50:00Z",
            },
            {
                "id": "m7",
                "from": "agent",
                "fromAgent": True,
                "name": STORE_NAME,
                "fromName": STORE_NAME,
                "body": "Glad it reached you, Ada.",
                "at": "2026-08-25T18:10:00Z",
            },
        ],
        "statusEvents": [
            {"at": "2026-08-25T18:12:00Z", "status": "closed", "note": "answered"},
        ],
    },
    {
        "id": "t-priya-unsub",
        "customerName": "Priya Lane",
        "subject": "Please unsubscribe me from marketing emails",
        "snippet": "Please take me off the marketing list. I still want order updates.",
        "status": "open",
        "assignee": "me",
        "updatedAt": "2026-08-28T15:40:00Z",
        "requestType": "marketing_unsubscribe",
        "messages": [
            {
                "id": "m8-unsub",
                "from": "customer",
                "fromAgent": False,
                "name": "Priya Lane",
                "fromName": "Priya Lane",
                "body": "Please take me off the marketing list. I still want order updates.",
                "at": "2026-08-28T15:40:00Z",
            }
        ],
        "statusEvents": [
            {"at": "2026-08-28T15:41:00Z", "status": "open", "note": "created"},
        ],
    },
    {
        "id": "t-lee-privacy",
        "customerName": "Lee Chen",
        "subject": "GDPR request — please delete my data",
        "snippet": "Please delete my stored personal data. I do not need a Shopify account change from this inbox.",
        "status": "open",
        "assignee": "me",
        "updatedAt": "2026-08-28T15:50:00Z",
        "requestType": "privacy_request",
        "privacySubtype": "delete",
        "privacyHandled": False,
        "messages": [
            {
                "id": "m9-privacy",
                "from": "customer",
                "fromAgent": False,
                "name": "Lee Chen",
                "fromName": "Lee Chen",
                "body": "Please delete my stored personal data. I do not need a Shopify account change from this inbox.",
                "at": "2026-08-28T15:50:00Z",
            }
        ],
        "statusEvents": [
            {"at": "2026-08-28T15:51:00Z", "status": "open", "note": "created"},
        ],
    },
    {
        "id": "t-remy-bug",
        "customerName": "Remy Cole",
        "subject": "App crash on iOS — checkout bug",
        "snippet": "The shop app crashes on iOS when I open checkout. I can keep using Android.",
        "status": "open",
        "assignee": "me",
        "updatedAt": "2026-08-28T16:00:00Z",
        "requestType": "bug",
        "severity": "high",
        "device": "iOS",
        "messages": [
            {
                "id": "m10-bug",
                "from": "customer",
                "fromAgent": False,
                "name": "Remy Cole",
                "fromName": "Remy Cole",
                "body": "The shop app crashes on iOS when I open checkout. I can keep using Android.",
                "at": "2026-08-28T16:00:00Z",
            }
        ],
        "statusEvents": [
            {"at": "2026-08-28T16:01:00Z", "status": "open", "note": "created"},
        ],
    },
) + tuple(DEMO_SEED_TICKETS)

_store: list[dict] = []
_intake: list[dict] = []
_by_dedupe: dict[tuple, dict] = {}
_seen_messages: set[str] = set()
_next_seq = 1


def _seen_file() -> Path | None:
    raw = os.environ.get("HELPDESK_SEEN_FILE", "").strip()
    return Path(raw) if raw else None


def _load_persisted_seen() -> None:
    path = _seen_file()
    if not path or not path.is_file():
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return
    if isinstance(data, list):
        for item in data:
            if item:
                _seen_messages.add(str(item))


def _persist_seen(message_id: str) -> None:
    path = _seen_file()
    if not path:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(sorted(_seen_messages)), encoding="utf-8")


def seed_catalog_loaded() -> bool:
    return len(_store) >= len(SEED_TICKETS)


def reset() -> None:
    global _store, _intake, _by_dedupe, _seen_messages, _next_seq
    _store = [copy.deepcopy(row) for row in SEED_TICKETS]
    _intake = []
    _by_dedupe = {}
    _seen_messages = set()
    _next_seq = 1
    _load_persisted_seen()


def remember_intake(record: dict) -> None:
    _intake.append(dict(record))
    message_id = record.get("messageId")
    if message_id:
        mid = str(message_id)
        _seen_messages.add(mid)
        _persist_seen(mid)


def seen_message_id(message_id: str | None) -> bool:
    return bool(message_id) and str(message_id) in _seen_messages


reset()


def intake_records() -> list[dict]:
    return [dict(row) for row in _intake]


def _snippet(body: str) -> str:
    return " ".join(str(body or "").split())[:140]


def infer_privacy_subtype(subject: str = "", body: str = "") -> str | None:
    """Optional Access / Delete / Export peek. Never a Shopify write."""
    hay = f"{subject or ''} {body or ''}".lower()
    if any(marker in hay for marker in ("delete my data", "data deletion", "erase my data", "right to be forgotten")):
        return "delete"
    if any(marker in hay for marker in ("export my data", "data export")):
        return "export"
    if any(marker in hay for marker in ("data request", "access my data", "access request")):
        return "access"
    return None


def infer_request_type(subject: str = "", body: str = "") -> str | None:
    """First-party type from intake subject/body. Never a Shopify write."""
    subject_hay = f"{subject or ''}".lower()
    hay = f"{subject or ''} {body or ''}".lower()
    if "unsubscribe-farm" in hay or "unsubscribe farm" in hay:
        return None
    if any(marker in hay for marker in _PRIVACY_MARKERS):
        return "privacy_request"
    if "unsubscribe" in subject_hay:
        return "marketing_unsubscribe"
    if _is_bug_copy(hay):
        return "bug"
    return None


def _is_bug_copy(hay: str) -> bool:
    if _BUG_TYPE_RE.search(hay):
        return True
    return bool(_BROKEN_RE.search(hay) and _TECH_RE.search(hay))


def infer_severity(subject: str = "", body: str = "") -> str | None:
    """Optional Low / Medium / High / Critical peek. Never a Shopify write."""
    hay = f"{subject or ''} {body or ''}"
    if _CRITICAL_RE.search(hay):
        return "critical"
    if _CRASH_RE.search(hay):
        return "high"
    if _LOW_RE.search(hay):
        return "low"
    return "medium"


def infer_device(subject: str = "", body: str = "") -> str | None:
    """Optional iOS / Android peek from intake keywords. Never a product mutation."""
    hay = f"{subject or ''} {body or ''}"
    if _IOS_RE.search(hay):
        return "iOS"
    if _ANDROID_RE.search(hay):
        return "Android"
    return None


def _normalize_request_type(
    value: str | None, subject: str = "", body: str = ""
) -> str | None:
    typed = str(value or "").strip() or infer_request_type(subject, body)
    if typed in REQUEST_TYPES:
        return typed
    return None


def _normalize_severity(value: str | None) -> str | None:
    raw = str(value or "").strip().lower()
    return raw if raw in SEVERITIES else None


def _normalize_device(value: str | None) -> str | None:
    text = " ".join(str(value or "").split())
    return text[:40] if text else None


def add_ticket(
    *,
    customer_name: str,
    subject: str,
    body: str,
    received_at: str,
    customer_id: str | None,
    order_id: str | None,
    channel: str,
    from_email: str | None,
    dedupe_key: tuple,
    request_type: str | None = None,
) -> dict:
    existing = _by_dedupe.get(dedupe_key)
    if existing:
        return _row(existing, gid_source="joined")
    global _next_seq
    ticket_id = f"t-in-{_next_seq}"
    _next_seq += 1
    typed = _normalize_request_type(request_type, subject, body)
    subtype = infer_privacy_subtype(subject, body) if typed == "privacy_request" else None
    severity = infer_severity(subject, body) if typed == "bug" else None
    device = infer_device(subject, body) if typed == "bug" else None
    ticket = {
        "id": ticket_id,
        "customerName": customer_name,
        "subject": subject,
        "snippet": _snippet(body),
        "status": "open",
        "assignee": None,
        "updatedAt": received_at,
        "joined": True,
        "customerId": customer_id,
        "orderId": order_id,
        "channel": channel,
        "fromEmail": from_email,
        "requestType": typed,
        "privacySubtype": subtype,
        "privacyHandled": False,
        "severity": severity,
        "device": device,
        "messages": [
            {
                "id": f"m-{ticket_id}-1",
                "from": "customer",
                "fromAgent": False,
                "name": customer_name,
                "fromName": customer_name,
                "body": body,
                "at": received_at,
            }
        ],
        "statusEvents": [
            {"at": received_at, "status": "open", "note": "created"},
        ],
    }
    if from_email:
        ticket["messages"][0]["fromEmail"] = from_email
    _store.insert(0, ticket)
    _by_dedupe[dedupe_key] = ticket
    return _row(ticket, gid_source="joined")


def _resolve_id(ticket_id: str) -> str:
    return ALIASES.get(str(ticket_id), str(ticket_id))


def _gids_for(ticket: dict, gid_source: str = "sample") -> tuple[str | None, str | None]:
    if ticket.get("joined"):
        return ticket.get("customerId"), ticket.get("orderId")
    table = LIVE_GIDS if gid_source in {"live", "live-holes"} else SAMPLE_GIDS
    return table.get(ticket["id"], (None, None))


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
    customer_id, order_id = _gids_for(ticket, gid_source)
    typed = ticket.get("requestType") or None
    severity = _normalize_severity(ticket.get("severity")) if typed == "bug" else None
    device = _normalize_device(ticket.get("device")) if typed == "bug" else None
    return {
        "id": ticket["id"],
        "customerName": project_customer_name(ticket),
        "subject": ticket["subject"],
        "snippet": ticket["snippet"],
        "status": ticket["status"],
        "updatedAt": ticket["updatedAt"],
        "customerId": customer_id,
        "orderId": order_id,
        "requestType": typed,
        "severity": severity,
        "device": device,
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
    rows = [t for t in _store if ticket_in_view(t, view)]
    return [_row(t, gid_source) for t in rows[:cap]]


def get_ticket(ticket_id: str, gid_source: str = "sample") -> dict:
    if not ticket_id:
        raise bad_request("ticketId is required", field="ticketId")
    canonical = _resolve_id(ticket_id)
    for ticket in _store:
        if ticket["id"] == canonical:
            row = _row(ticket, gid_source)
            row["messages"] = [project_message(ticket, message) for message in ticket["messages"]]
            row["statusEvents"] = [dict(event) for event in ticket["statusEvents"]]
            row["escalated"] = bool(ticket.get("escalated"))
            reason = ticket.get("escalationReason")
            if reason:
                row["escalationReason"] = str(reason)
            if ticket.get("fromEmail"):
                row["fromEmail"] = ticket.get("fromEmail")
            subtype = ticket.get("privacySubtype") if row.get("requestType") == "privacy_request" else None
            row["privacySubtype"] = subtype if subtype in PRIVACY_SUBTYPES else None
            row["privacyHandled"] = bool(ticket.get("privacyHandled"))
            return row
    raise not_found("ticket", str(ticket_id))


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def escalate_ticket(ticket_id: str, reason: str | None = None, gid_source: str = "sample") -> dict:
    """First-party helpdesk escalate. Never a Shopify mutation."""
    if not ticket_id:
        raise bad_request("ticketId is required", field="ticketId")
    canonical = _resolve_id(ticket_id)
    note_reason = " ".join(str(reason or "").split())
    for ticket in _store:
        if ticket["id"] != canonical:
            continue
        now = _now_iso()
        already = bool(ticket.get("escalated"))
        ticket["escalated"] = True
        if note_reason:
            ticket["escalationReason"] = note_reason[:240]
        ticket["updatedAt"] = now
        if not already:
            note = "escalated"
            if note_reason:
                note = f"escalated: {note_reason}"[:140]
            ticket.setdefault("statusEvents", []).append(
                {"at": now, "status": ticket["status"], "note": note}
            )
        return get_ticket(canonical, gid_source)
    raise not_found("ticket", str(ticket_id))


def mark_privacy_handled(ticket_id: str, gid_source: str = "sample") -> dict:
    """First-party helpdesk flag. Never a Shopify Customer Privacy write."""
    if not ticket_id:
        raise bad_request("ticketId is required", field="ticketId")
    canonical = _resolve_id(ticket_id)
    for ticket in _store:
        if ticket["id"] != canonical:
            continue
        if ticket.get("requestType") != "privacy_request":
            raise bad_request("ticket is not a privacy request", field="ticketId")
        now = _now_iso()
        already = bool(ticket.get("privacyHandled"))
        ticket["privacyHandled"] = True
        ticket["updatedAt"] = now
        if not already:
            ticket.setdefault("statusEvents", []).append(
                {"at": now, "status": ticket["status"], "note": "privacy handled"}
            )
        return get_ticket(canonical, gid_source)
    raise not_found("ticket", str(ticket_id))
