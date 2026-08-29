"""Fixture returns tissue for the inbox rail.

INPUT: ticket id.
OUTPUT: Order.returns + Order.returnStatus, or an empty degrade.
Sandbox shape: returns.nodes is empty and returnStatus is NO_RETURN.
Not a live returns-provider integration. No network calls.
"""

from __future__ import annotations

from .types import EMPTY_RETURNS, OrderReturns, TissueResult

_EMPTY = OrderReturns(returns=EMPTY_RETURNS, returnStatus="NO_RETURN")


def health() -> str:
    return "healthy"


def get_return_context(ticket_id: str) -> TissueResult:
    del ticket_id
    return TissueResult(
        status="empty",
        data=_EMPTY,
        empty_reason="No return in progress.",
    )
