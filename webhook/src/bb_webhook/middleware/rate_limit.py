"""Bounded sliding-window rate limiting for authenticated webhooks."""

from __future__ import annotations

import time
from collections import deque
from typing import Callable

_MAX_REQUESTS_PER_MINUTE = 60
_WINDOW_SECONDS = 60.0
_rate_window: deque[tuple[float, str]] = deque()


class SlidingWindowRateLimiter:
    """A small deterministic limiter suitable for unit tests and ASGI use."""

    def __init__(
        self,
        max_requests: int,
        window_seconds: float = _WINDOW_SECONDS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if max_requests < 1:
            raise ValueError("max_requests must be positive")
        if window_seconds <= 0:
            raise ValueError("window_seconds must be positive")
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.clock = clock
        self.window: deque[tuple[float, str]] = deque()

    def allow(self, client_ip: str) -> bool:
        now = self.clock()
        cutoff = now - self.window_seconds
        while self.window and self.window[0][0] < cutoff:
            self.window.popleft()
        count = sum(1 for _timestamp, ip in self.window if ip == client_ip)
        if count >= self.max_requests:
            return False
        self.window.append((now, client_ip))
        return True


def _check_rate_limit(client_ip: str, max_requests: int | None = None) -> bool:
    """Return whether *client_ip* remains within the one-minute window."""
    request_limit = _MAX_REQUESTS_PER_MINUTE if max_requests is None else max_requests
    if request_limit < 1:
        return False
    now = time.monotonic()
    cutoff = now - _WINDOW_SECONDS
    while _rate_window and _rate_window[0][0] < cutoff:
        _rate_window.popleft()
    count = sum(1 for _timestamp, ip in _rate_window if ip == client_ip)
    if count >= request_limit:
        return False
    _rate_window.append((now, client_ip))
    return True
