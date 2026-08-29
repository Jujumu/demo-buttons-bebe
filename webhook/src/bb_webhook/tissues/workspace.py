"""Module 9 — Team Support Workspace organ.

INPUT: view id, ticket id, composer body, insert/discard/send requests.
OUTPUT: inbox snapshot, composed ticket workspace, or a human send result.
Composes fixture tickets, identity, Shopify DTO, returns, and drafts.
If Shopify context fails, the thread still returns.
Never auto-sends. Never issues Edit / Refund / Cancel.
Never calls a live shop or returns provider.
"""

from __future__ import annotations

from typing import Any

from . import drafts, identity, returns, shopify_context, tickets
from .types import InboxSnapshot, TicketWorkspace, TissueResult


def health() -> dict[str, str]:
    return {
        "workspace": "healthy",
        "tickets": tickets.health(),
        "identity": identity.health(),
        "shopify_context": shopify_context.health(),
        "returns": returns.health(),
        "drafts": drafts.health(),
    }


def inbox(view_id: str) -> InboxSnapshot:
    return InboxSnapshot(
        source="fixture",
        views=tickets.list_views(),
        tickets=tickets.list_tickets(view_id),
    )


def open_ticket(ticket_id: str, *, retry_shopify: bool = False) -> TissueResult:
    summary = tickets.get_ticket(ticket_id)
    if summary is None:
        return TissueResult(status="empty", empty_reason="This ticket is not in the workspace.")
    shopify = (
        shopify_context.retry_order_context(ticket_id)
        if retry_shopify
        else shopify_context.get_order_context(ticket_id)
    )
    past = (
        shopify_context.get_past_orders(ticket_id)
        if shopify.status != "error"
        else TissueResult(status="error", error="Shopify context is unavailable.")
    )
    workspace = TicketWorkspace(
        ticket=summary,
        thread=tickets.get_thread(ticket_id),
        identity=identity.get_identity(ticket_id),
        shopify=shopify,
        returns=returns.get_return_context(ticket_id),
        draft=drafts.get_draft(ticket_id),
        past_orders=past,
        macros=drafts.list_macros(),
    )
    return TissueResult(status="ok", data=workspace)


def insert_draft(ticket_id: str) -> dict[str, Any]:
    result = drafts.insert_draft(ticket_id)
    return {
        "sent": False,
        "action": "insert",
        "draft": result.as_dict(),
    }


def discard_draft(ticket_id: str) -> dict[str, Any]:
    result = drafts.discard_draft(ticket_id)
    return {
        "sent": False,
        "action": "discard",
        "draft": result.as_dict(),
    }


def send_reply(ticket_id: str, body: str, close: bool = False) -> TissueResult:
    """Human-gated send. The draft tissue cannot reach this function."""
    return tickets.apply_human_send(ticket_id, body, close)
