"""Mint a 24h Admin token via client_credentials. Never log or return the token."""

from __future__ import annotations

import json
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .errors import HelpdeskError

_cache: dict[str, object] = {"token": None, "expires_at": 0.0, "shop": ""}


def mint_token(shop: str, client_id: str, client_secret: str) -> str:
    body = json.dumps(
        {
            "client_id": client_id,
            "client_secret": client_secret,
            "grant_type": "client_credentials",
        }
    ).encode("utf-8")
    request = Request(
        f"https://{shop}/admin/oauth/access_token",
        data=body,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise HelpdeskError("auth_failed", "Shopify token mint failed") from exc
    except (URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise HelpdeskError("auth_failed", "Shopify token mint failed") from exc
    token = payload.get("access_token")
    if not token or not isinstance(token, str):
        raise HelpdeskError("auth_failed", "Shopify token mint failed")
    expires_in = int(payload.get("expires_in") or 86400)
    _cache["token"] = token
    _cache["expires_at"] = time.time() + max(expires_in - 300, 60)
    _cache["shop"] = shop
    return token


def cached_token(shop: str, client_id: str, client_secret: str) -> str:
    if _cache["token"] and _cache["shop"] == shop and float(_cache["expires_at"]) > time.time():
        return str(_cache["token"])
    return mint_token(shop, client_id, client_secret)


def clear_token_cache() -> None:
    _cache.update({"token": None, "expires_at": 0.0, "shop": ""})
