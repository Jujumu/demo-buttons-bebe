"""Shopify GID helpers. Rail tools accept full GIDs only."""

from __future__ import annotations

import re

from .errors import bad_request

_GID = re.compile(r"^gid://shopify/(Customer|Order|Return)/[0-9]+$")


def require_gid(value: str | None, expected: str) -> str:
    if not value or not isinstance(value, str):
        raise bad_request(f"{expected} GID is required", field=expected)
    ident = value.strip()
    if not _GID.match(ident):
        raise bad_request(
            f"{expected} must be a Shopify GID (gid://shopify/{expected}/…)",
            field=expected,
        )
    kind = ident.split("/")[3]
    if kind != expected:
        raise bad_request(f"{expected} GID required", field=expected, got=kind)
    return ident


def require_shop(value: str | None) -> str:
    if not value or not isinstance(value, str) or not value.strip():
        raise bad_request("shop is required", field="shop")
    shop = value.strip().lower()
    if "/" in shop or " " in shop:
        raise bad_request("shop must be a hostname", field="shop")
    return shop
