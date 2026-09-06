"""Detachable Gorgias bridge sidecar.

Gorgias-specific modules live here so helpdesk/ never imports gorgias_*.
Neutral config and routing are safe for helpdesk tissues to call.
"""

from __future__ import annotations

__all__ = ["config", "router"]
