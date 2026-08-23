"""Fail-closed network guards used only when ``DEMO_MODE=1``.

Production keeps its existing destinations.  Demo mode is stricter: a typo or
an inherited client environment must never turn a localhost simulation into an
external request.
"""

from __future__ import annotations

import os
from urllib.parse import urlsplit


_TRUE_VALUES = {"1", "true", "yes", "on"}
_LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}


def demo_mode_enabled() -> bool:
    return os.environ.get("DEMO_MODE", "").strip().lower() in _TRUE_VALUES


def demo_url_allowed(
    url: str,
    *,
    port: int,
    exact_path: str | None = None,
    path_prefix: str | None = None,
) -> bool:
    """Return whether a demo destination is the expected loopback endpoint."""

    if not demo_mode_enabled():
        return True
    try:
        parsed = urlsplit(url)
        if (
            parsed.scheme != "http"
            or parsed.hostname not in _LOOPBACK_HOSTS
            or parsed.port != port
            or parsed.username is not None
            or parsed.password is not None
            or parsed.fragment
        ):
            return False
    except (TypeError, ValueError):
        return False
    if exact_path is not None and parsed.path != exact_path:
        return False
    if path_prefix is not None and not parsed.path.startswith(path_prefix):
        return False
    return True
