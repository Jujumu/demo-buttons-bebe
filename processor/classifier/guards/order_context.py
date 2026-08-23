"""Evidence that a weak phrase refers to a real order."""

from __future__ import annotations

import re


_ORDER_CONTEXT_RE = re.compile(
    r"\b("
    r"arrived|delivered|delivery|received|came\s+(?:in|today|yesterday)|"
    r"parcel|parcels|package|packages|shipment|the\s+box|my\s+box|in\s+the\s+box|"
    r"tracking|courier|dispatched|"
    r"my\s+(?:order|purchase|item|items|delivery|parcel|package)|"
    r"order[\s#]*\d|#\s*\d{3,}"
    r")\b",
    re.IGNORECASE,
)


__all__ = ["_ORDER_CONTEXT_RE"]
