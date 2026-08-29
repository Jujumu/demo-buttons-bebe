"""Public DTOs shared at tissue boundaries. No tissue owns another tissue."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

TissueStatus = Literal["ok", "empty", "error", "unavailable"]
TicketStatus = Literal["open", "closed", "snoozed"]
MessageKind = Literal["customer", "agent", "status"]


def _public(obj: Any) -> Any:
    if hasattr(obj, "as_dict"):
        return obj.as_dict()
    if isinstance(obj, list):
        return [_public(item) for item in obj]
    if isinstance(obj, dict):
        return {key: _public(value) for key, value in obj.items()}
    return obj


@dataclass(frozen=True)
class TissueResult:
    """Uniform envelope so a failed tissue cannot invent a successful payload."""

    status: TissueStatus
    data: Any = None
    error: str | None = None
    empty_reason: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "data": _public(self.data),
            "error": self.error,
            "empty_reason": self.empty_reason,
        }


@dataclass(frozen=True)
class TicketSummary:
    id: str
    view_ids: tuple[str, ...]
    customer_name: str
    subject: str
    snippet: str
    updated_label: str
    status: TicketStatus
    assigned_to: str | None
    unread: bool = False

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["view_ids"] = list(self.view_ids)
        return payload


@dataclass(frozen=True)
class Message:
    id: str
    kind: MessageKind
    author: str
    body: str
    at_label: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Thread:
    ticket_id: str
    subject: str
    status: TicketStatus
    assigned_to: str | None
    customer_name: str
    messages: tuple[Message, ...]
    summary: str
    message_count: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "ticket_id": self.ticket_id,
            "subject": self.subject,
            "status": self.status,
            "assigned_to": self.assigned_to,
            "customer_name": self.customer_name,
            "messages": [message.as_dict() for message in self.messages],
            "summary": self.summary,
            "message_count": self.message_count,
        }


@dataclass(frozen=True)
class CustomerProfile:
    display_name: str
    email: str
    phone: str | None
    notes: str
    identified: bool

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class OrderLine:
    title: str
    sku: str
    quantity: int
    price: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Address:
    label: str
    name: str
    lines: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {"label": self.label, "name": self.name, "lines": list(self.lines)}


@dataclass(frozen=True)
class Shipment:
    tracking_number: str
    tracking_url: str
    tracking_label: str
    carrier: str
    status: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ShopifyOrder:
    """Support-facing Shopify DTO. Source of truth remains Shopify."""

    order_number: str
    financial_status: str
    fulfillment_status: str
    created_label: str
    currency: str
    subtotal: str
    shipping: str
    tax: str
    total: str
    lines: tuple[OrderLine, ...]
    addresses: tuple[Address, ...]
    shipment: Shipment | None
    freshness_label: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "order_number": self.order_number,
            "financial_status": self.financial_status,
            "fulfillment_status": self.fulfillment_status,
            "created_label": self.created_label,
            "currency": self.currency,
            "subtotal": self.subtotal,
            "shipping": self.shipping,
            "tax": self.tax,
            "total": self.total,
            "lines": [line.as_dict() for line in self.lines],
            "addresses": [address.as_dict() for address in self.addresses],
            "shipment": None if self.shipment is None else self.shipment.as_dict(),
            "freshness_label": self.freshness_label,
        }


@dataclass(frozen=True)
class PastOrder:
    order_number: str
    date_label: str
    total: str
    status: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ReturnRecord:
    return_id: str
    in_progress: bool
    stage: str
    next_step: str
    refund_status: str
    freshness_label: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Draft:
    ticket_id: str
    text: str
    language: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Macro:
    id: str
    title: str
    body: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class View:
    id: str
    label: str
    count: int

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class InboxSnapshot:
    source: str
    views: tuple[View, ...]
    tickets: tuple[TicketSummary, ...]
    selected_id: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "views": [view.as_dict() for view in self.views],
            "tickets": [ticket.as_dict() for ticket in self.tickets],
            "selected_id": self.selected_id,
        }


@dataclass(frozen=True)
class TicketWorkspace:
    ticket: TicketSummary
    thread: TissueResult
    identity: TissueResult
    shopify: TissueResult
    returns: TissueResult
    draft: TissueResult
    past_orders: TissueResult
    macros: tuple[Macro, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict[str, Any]:
        return {
            "ticket": self.ticket.as_dict(),
            "thread": self.thread.as_dict(),
            "identity": self.identity.as_dict(),
            "shopify": self.shopify.as_dict(),
            "returns": self.returns.as_dict(),
            "draft": self.draft.as_dict(),
            "past_orders": self.past_orders.as_dict(),
            "macros": [macro.as_dict() for macro in self.macros],
        }
