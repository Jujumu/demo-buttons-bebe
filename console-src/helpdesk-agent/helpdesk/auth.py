"""Mint a 24h Admin token. Shop comes from SHOPIFY_SHOP only. No redirect follow."""

from __future__ import annotations

import json
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .env import load_shopify_env
from .errors import HelpdeskError
from .names import LIVE_HOLE_SHOP

PINNED_LIVE_SHOP = LIVE_HOLE_SHOP
_TOKEN_PATH = "/admin/oauth/access_token"

_cache: dict[str, object] = {"token": None, "expires_at": 0.0, "shop": ""}


def normalize_shop(value: str | None) -> str:
    text = (value or "").strip().strip("\"'").replace("\r", "")
    lowered = text.lower()
    for prefix in ("https://", "http://"):
        if lowered.startswith(prefix):
            text = text[len(prefix) :]
            lowered = text.lower()
            break
    host = lowered.split("/", 1)[0].split("?", 1)[0].rstrip(".")
    return host.rstrip("/")


def shop_from_env(env: dict[str, str] | None = None) -> str:
    if env is None:
        env = load_shopify_env()
    return normalize_shop(env.get("SHOPIFY_SHOP", ""))


def require_pinned_shop(env: dict[str, str] | None = None) -> str:
    shop = shop_from_env(env)
    if not shop:
        raise HelpdeskError("auth_failed", "Shopify shop is not configured")
    if shop != PINNED_LIVE_SHOP:
        raise HelpdeskError("auth_failed", "Shopify shop is not the pinned live host")
    return shop


class _RefuseRedirects(HTTPRedirectHandler):
    """Never follow 3xx on the client_credentials POST."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        raise HelpdeskError("auth_failed", "Shopify token mint refused a redirect")


def token_opener():
    return build_opener(_RefuseRedirects())


def _auth_failed() -> HelpdeskError:
    return HelpdeskError("auth_failed", "Shopify token mint failed")


def mint_token(
    client_id: str,
    client_secret: str,
    *,
    env: dict[str, str] | None = None,
    opener: Any | None = None,
) -> str:
    shop = require_pinned_shop(env)
    if not client_id or not client_secret:
        raise _auth_failed()
    body = json.dumps(
        {
            "client_id": client_id,
            "client_secret": client_secret,
            "grant_type": "client_credentials",
        }
    ).encode("utf-8")
    request = Request(
        f"https://{shop}{_TOKEN_PATH}",
        data=body,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with (opener or token_opener()).open(request, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HelpdeskError:
        raise
    except HTTPError as exc:
        raise _auth_failed() from exc
    except (URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        raise _auth_failed() from exc
    token = payload.get("access_token")
    if not token or not isinstance(token, str):
        raise _auth_failed()
    expires_in = int(payload.get("expires_in") or 86400)
    _cache["token"] = token
    _cache["expires_at"] = time.time() + max(expires_in - 300, 60)
    _cache["shop"] = shop
    return token


def cached_token(
    client_id: str,
    client_secret: str,
    *,
    env: dict[str, str] | None = None,
    opener: Any | None = None,
) -> str:
    shop = require_pinned_shop(env)
    if _cache["token"] and _cache["shop"] == shop and float(_cache["expires_at"]) > time.time():
        return str(_cache["token"])
    return mint_token(client_id, client_secret, env=env, opener=opener)


def clear_token_cache() -> None:
    _cache.update({"token": None, "expires_at": 0.0, "shop": ""})
