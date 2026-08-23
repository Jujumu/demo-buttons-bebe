"""Shared localhost assertion for demo dependency servers."""

from __future__ import annotations


LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}


def require_loopback(host: str, service: str) -> str:
    if host not in LOOPBACK_HOSTS:
        raise RuntimeError(f"{service} refuses non-loopback host {host!r}")
    return host
