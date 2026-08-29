"""Module 2 — Ticket and Conversation (fixture).

INPUT: view id, ticket id, or a send request (body + close flag).
OUTPUT: ticket summaries, a thread, or an updated thread after a human send.
Does not look up Shopify/Redo, write drafts, or send through a provider.
"""

from __future__ import annotations

from copy import deepcopy

from .types import Message, TicketStatus, TicketSummary, TissueResult, Thread, View

VIEWS: tuple[View, ...] = (
    View("assigned", "Assigned to me", 0),
    View("unassigned", "Unassigned", 0),
    View("open", "Open", 0),
    View("closed", "Closed", 0),
    View("snoozed", "Snoozed", 0),
    View("all", "All", 0),
)

_DEFAULT_TICKETS: dict[str, TicketSummary] = {
    "tk-1001": TicketSummary(
        id="tk-1001",
        view_ids=("assigned", "open", "all"),
        customer_name="Jane Example",
        subject="Where is order 1001?",
        snippet="Has the cotton onesie shipped yet?",
        updated_label="2h",
        status="open",
        assigned_to="You",
    ),
    "tk-1002": TicketSummary(
        id="tk-1002",
        view_ids=("unassigned", "open", "all"),
        customer_name="Alex Patron",
        subject="Need a size for order 1002",
        snippet="What size is the romper on this order?",
        updated_label="5h",
        status="open",
        assigned_to=None,
    ),
    "tk-1003": TicketSummary(
        id="tk-1003",
        view_ids=("assigned", "open", "all"),
        customer_name="Sam Reviewer",
        subject="Question about fabric care",
        snippet="How should I wash the sample set?",
        updated_label="1d",
        status="open",
        assigned_to="You",
    ),
    "tk-1004": TicketSummary(
        id="tk-1004",
        view_ids=("assigned", "open", "all"),
        customer_name="Riley Return",
        subject="Return for order 1004",
        snippet="I started a return in the portal.",
        updated_label="3h",
        status="open",
        assigned_to="You",
    ),
    "tk-1005": TicketSummary(
        id="tk-1005",
        view_ids=("closed", "all"),
        customer_name="Casey Closed",
        subject="Thanks for order 1005",
        snippet="All set — thank you!",
        updated_label="4d",
        status="closed",
        assigned_to="You",
    ),
    "tk-1006": TicketSummary(
        id="tk-1006",
        view_ids=("unassigned", "open", "all"),
        customer_name="Unknown sender",
        subject="Is this the right inbox?",
        snippet="I bought something last month.",
        updated_label="6h",
        status="open",
        assigned_to=None,
    ),
}

_DEFAULT_THREADS: dict[str, list[Message]] = {
    "tk-1001": [
        Message("m1", "customer", "Jane Example",
                "Hi — I placed order 1001. Has the cotton onesie shipped yet?", "Tue 9:14"),
        Message("m2", "status", "System", "Ticket opened and assigned to you.", "Tue 9:14"),
        Message("m3", "agent", "You",
                "Thanks Jane — I am checking the shipment and will reply with the tracking link.", "Tue 9:40"),
        Message("m4", "customer", "Jane Example",
                "Appreciate it. The confirmation only shows paid so far.", "Tue 10:02"),
    ],
    "tk-1002": [
        Message("m1", "customer", "Alex Patron",
                "What size is the romper on order 1002? I want to order a second one.", "Mon 16:20"),
        Message("m2", "status", "System", "Ticket opened. Unassigned.", "Mon 16:20"),
    ],
    "tk-1003": [
        Message("m1", "customer", "Sam Reviewer",
                "How should I wash the sample set? Cold water okay?", "Sun 11:05"),
        Message("m2", "status", "System", "Ticket opened and assigned to you.", "Sun 11:05"),
    ],
    "tk-1004": [
        Message("m1", "customer", "Riley Return",
                "I started a return for order 1004 in the returns portal. Is it moving?", "Tue 8:01"),
        Message("m2", "status", "System", "Ticket opened and assigned to you.", "Tue 8:01"),
    ],
    "tk-1005": [
        Message("m1", "customer", "Casey Closed", "Just confirming order 1005 arrived. Thank you!", "Thu 14:12"),
        Message("m2", "agent", "You", "Glad it arrived, Casey. Enjoy the set.", "Thu 14:40"),
        Message("m3", "status", "System", "Ticket closed.", "Thu 14:40"),
    ],
    "tk-1006": [
        Message("m1", "customer", "Unknown sender",
                "I bought something last month and the note is not on this email. Can you still help?", "Tue 7:55"),
        Message("m2", "status", "System", "Ticket opened. Customer is unidentified.", "Tue 7:55"),
    ],
}

_SUMMARIES = {
    "tk-1001": "Jane Example is asking whether order 1001 has shipped.",
    "tk-1002": "Alex Patron wants the romper size on order 1002.",
    "tk-1003": "Sam Reviewer asked how to wash the sample set.",
    "tk-1004": "Riley Return wants the status of an in-progress return.",
    "tk-1005": "Casey Closed confirmed delivery; ticket is closed.",
    "tk-1006": "Unidentified sender asked about a past purchase.",
}

_tickets: dict[str, TicketSummary] = {}
_threads: dict[str, list[Message]] = {}


def reset_fixtures() -> None:
    """Test helper. Other tissues must not call this."""
    global _tickets, _threads
    _tickets = dict(_DEFAULT_TICKETS)
    _threads = {key: list(messages) for key, messages in _DEFAULT_THREADS.items()}


reset_fixtures()


def health() -> str:
    return "healthy"


def list_views() -> tuple[View, ...]:
    counts = {view.id: 0 for view in VIEWS}
    for ticket in _tickets.values():
        for view_id in ticket.view_ids:
            if view_id in counts:
                counts[view_id] += 1
    return tuple(View(view.id, view.label, counts[view.id]) for view in VIEWS)


def list_tickets(view_id: str) -> tuple[TicketSummary, ...]:
    wanted = view_id if view_id in {view.id for view in VIEWS} else "open"
    return tuple(
        deepcopy(ticket)
        for ticket in _tickets.values()
        if wanted in ticket.view_ids
    )


def get_ticket(ticket_id: str) -> TicketSummary | None:
    ticket = _tickets.get(ticket_id)
    return None if ticket is None else deepcopy(ticket)


def get_thread(ticket_id: str) -> TissueResult:
    ticket = _tickets.get(ticket_id)
    messages = _threads.get(ticket_id)
    if ticket is None or messages is None:
        return TissueResult(status="empty", empty_reason="This ticket is not in the workspace.")
    thread = Thread(
        ticket_id=ticket.id,
        subject=ticket.subject,
        status=ticket.status,
        assigned_to=ticket.assigned_to,
        customer_name=ticket.customer_name,
        messages=tuple(messages),
        summary=_SUMMARIES.get(ticket_id, ""),
        message_count=len(messages),
    )
    return TissueResult(status="ok", data=thread)


def apply_human_send(ticket_id: str, body: str, close: bool) -> TissueResult:
    """Record a human-initiated public reply. Never auto-sends."""
    text = body.strip()
    if not text:
        return TissueResult(status="error", error="Send is disabled until the reply has body text.")
    ticket = _tickets.get(ticket_id)
    messages = _threads.get(ticket_id)
    if ticket is None or messages is None:
        return TissueResult(status="empty", empty_reason="This ticket is not in the workspace.")
    next_id = f"m{len(messages) + 1}"
    messages.append(Message(next_id, "agent", "You", text, "Just now"))
    snippet = text if len(text) <= 72 else text[:69] + "…"
    new_status: TicketStatus = "closed" if close else ticket.status
    view_ids = ticket.view_ids
    if close:
        view_ids = tuple(
            view_id for view_id in ticket.view_ids if view_id not in {"open", "unassigned", "assigned"}
        ) + (("closed",) if "closed" not in ticket.view_ids else ())
        if "all" not in view_ids:
            view_ids = view_ids + ("all",)
        messages.append(Message(f"m{len(messages) + 1}", "status", "System", "Ticket closed.", "Just now"))
    _tickets[ticket_id] = TicketSummary(
        id=ticket.id,
        view_ids=view_ids,
        customer_name=ticket.customer_name,
        subject=ticket.subject,
        snippet=snippet,
        updated_label="now",
        status=new_status,
        assigned_to=ticket.assigned_to or "You",
    )
    return get_thread(ticket_id)
