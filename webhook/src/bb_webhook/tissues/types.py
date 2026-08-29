"""Public DTOs shared at tissue boundaries. No tissue owns another tissue.

Shopify rail keys are Admin GraphQL 2026-07 names from a validated
read-only query (see ``RAIL_LOCK_QUERY``). Do not invent fields.
Runtime payloads are fixtures in the development-store sandbox shape:
three AI-DEMO customers, paid ``#1002``–``#1004``, null ``sku``,
empty ``returns``, ``billingAddress`` often null.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

TissueStatus = Literal["ok", "empty", "error", "unavailable"]
TicketStatus = Literal["open", "closed", "snoozed"]
MessageKind = Literal["customer", "agent", "status"]

RAIL_LOCK_API_VERSION = "2026-07"
CUSTOMER_RAIL_FIELDS = (
    "displayName",
    "defaultEmailAddress",
    "numberOfOrders",
    "amountSpent",
)
ORDER_RAIL_FIELDS = (
    "name",
    "displayFinancialStatus",
    "displayFulfillmentStatus",
    "currentTotalPriceSet",
    "lineItems",
    "shippingAddress",
    "billingAddress",
    "fulfillments",
    "returns",
    "returnStatus",
)
RAIL_LOCK_QUERY = """
query RailLock {
  customers(first: 10, query: "email:ai-demo") {
    nodes {
      displayName
      defaultEmailAddress { emailAddress }
      numberOfOrders
      amountSpent { amount currencyCode }
    }
  }
  orders(first: 10, query: "name:#1002 OR name:#1003 OR name:#1004") {
    nodes {
      name
      displayFinancialStatus
      displayFulfillmentStatus
      currentTotalPriceSet {
        shopMoney { amount currencyCode }
        presentmentMoney { amount currencyCode }
      }
      lineItems(first: 20) {
        nodes { name sku quantity }
      }
      shippingAddress { name address1 address2 city province zip country formatted }
      billingAddress { name address1 address2 city province zip country formatted }
      fulfillments(first: 10) {
        trackingInfo { company number url }
      }
      returns(first: 10) { nodes { name status } }
      returnStatus
    }
  }
}
"""


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
class CustomerEmailAddress:
    """Customer.defaultEmailAddress — never Customer.email (deprecated)."""

    emailAddress: str

    def as_dict(self) -> dict[str, Any]:
        return {"emailAddress": self.emailAddress}


@dataclass(frozen=True)
class MoneyV2:
    amount: str
    currencyCode: str

    def as_dict(self) -> dict[str, Any]:
        return {"amount": self.amount, "currencyCode": self.currencyCode}


@dataclass(frozen=True)
class MoneyBag:
    shopMoney: MoneyV2
    presentmentMoney: MoneyV2

    def as_dict(self) -> dict[str, Any]:
        return {
            "shopMoney": self.shopMoney.as_dict(),
            "presentmentMoney": self.presentmentMoney.as_dict(),
        }


def money_bag(amount: str, currency_code: str = "USD") -> MoneyBag:
    money = MoneyV2(amount=amount, currencyCode=currency_code)
    return MoneyBag(shopMoney=money, presentmentMoney=money)


@dataclass(frozen=True)
class CustomerProfile:
    displayName: str
    defaultEmailAddress: CustomerEmailAddress | None
    numberOfOrders: str
    amountSpent: MoneyV2

    def as_dict(self) -> dict[str, Any]:
        return {
            "displayName": self.displayName,
            "defaultEmailAddress": None
            if self.defaultEmailAddress is None
            else self.defaultEmailAddress.as_dict(),
            "numberOfOrders": self.numberOfOrders,
            "amountSpent": self.amountSpent.as_dict(),
        }


@dataclass(frozen=True)
class LineItemNode:
    name: str
    sku: str | None
    quantity: int

    def as_dict(self) -> dict[str, Any]:
        return {"name": self.name, "sku": self.sku, "quantity": self.quantity}


@dataclass(frozen=True)
class LineItemConnection:
    nodes: tuple[LineItemNode, ...]

    def as_dict(self) -> dict[str, Any]:
        return {"nodes": [node.as_dict() for node in self.nodes]}


@dataclass(frozen=True)
class MailingAddress:
    name: str | None
    address1: str | None
    address2: str | None
    city: str | None
    province: str | None
    zip: str | None
    country: str | None
    formatted: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "address1": self.address1,
            "address2": self.address2,
            "city": self.city,
            "province": self.province,
            "zip": self.zip,
            "country": self.country,
            "formatted": list(self.formatted),
        }


@dataclass(frozen=True)
class FulfillmentTrackingInfo:
    company: str | None
    number: str | None
    url: str | None

    def as_dict(self) -> dict[str, Any]:
        return {"company": self.company, "number": self.number, "url": self.url}


@dataclass(frozen=True)
class Fulfillment:
    trackingInfo: tuple[FulfillmentTrackingInfo, ...]

    def as_dict(self) -> dict[str, Any]:
        return {"trackingInfo": [info.as_dict() for info in self.trackingInfo]}


@dataclass(frozen=True)
class ReturnNode:
    name: str
    status: str

    def as_dict(self) -> dict[str, Any]:
        return {"name": self.name, "status": self.status}


@dataclass(frozen=True)
class ReturnConnection:
    nodes: tuple[ReturnNode, ...]

    def as_dict(self) -> dict[str, Any]:
        return {"nodes": [node.as_dict() for node in self.nodes]}


EMPTY_RETURNS = ReturnConnection(nodes=())


@dataclass(frozen=True)
class ShopifyOrder:
    """Support-facing Shopify DTO. Keys match Admin GraphQL 2026-07."""

    name: str
    displayFinancialStatus: str
    displayFulfillmentStatus: str
    currentTotalPriceSet: MoneyBag
    lineItems: LineItemConnection
    shippingAddress: MailingAddress | None
    billingAddress: MailingAddress | None
    fulfillments: tuple[Fulfillment, ...]
    returns: ReturnConnection
    returnStatus: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "displayFinancialStatus": self.displayFinancialStatus,
            "displayFulfillmentStatus": self.displayFulfillmentStatus,
            "currentTotalPriceSet": self.currentTotalPriceSet.as_dict(),
            "lineItems": self.lineItems.as_dict(),
            "shippingAddress": None
            if self.shippingAddress is None
            else self.shippingAddress.as_dict(),
            "billingAddress": None
            if self.billingAddress is None
            else self.billingAddress.as_dict(),
            "fulfillments": [fulfillment.as_dict() for fulfillment in self.fulfillments],
            "returns": self.returns.as_dict(),
            "returnStatus": self.returnStatus,
        }


@dataclass(frozen=True)
class PastOrder:
    name: str
    displayFinancialStatus: str
    displayFulfillmentStatus: str
    currentTotalPriceSet: MoneyBag

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "displayFinancialStatus": self.displayFinancialStatus,
            "displayFulfillmentStatus": self.displayFulfillmentStatus,
            "currentTotalPriceSet": self.currentTotalPriceSet.as_dict(),
        }


@dataclass(frozen=True)
class OrderReturns:
    """Order.returns + Order.returnStatus. Empty nodes is the sandbox shape."""

    returns: ReturnConnection
    returnStatus: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "returns": self.returns.as_dict(),
            "returnStatus": self.returnStatus,
        }


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
