"""Replaceable support tissues with explicit public contracts.

A tissue is a black box: defined input, defined output, no cross-module
internals. The workspace organ composes them. See each module's INPUT/OUTPUT
docstring and ``contracts.md`` in the pull request.
"""

from . import drafts, identity, returns, shopify_context, tickets, workspace

__all__ = [
    "drafts",
    "identity",
    "returns",
    "shopify_context",
    "tickets",
    "workspace",
]
