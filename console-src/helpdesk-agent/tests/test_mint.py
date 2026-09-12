from __future__ import annotations

import json
import unittest
from email.message import Message
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import BaseHandler, Request, build_opener
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from helpdesk.auth import (
    _RefuseRedirects,
    clear_token_cache,
    mint_token,
    normalize_shop,
    require_configured_shop,
    require_pinned_shop,
    token_opener,
)
from helpdesk.client import graphql
from helpdesk.errors import HelpdeskError
from helpdesk.names import LIVE_HOLE_SHOP
from helpdesk.shop import _can_mint
from helpdesk import join as join_mod

DEMO = LIVE_HOLE_SHOP
BUYER = "buyer-shop.myshopify.com"
_DUMMY_ID = "test-client-id"
_DUMMY_SECRET = "test-client-secret"
_DUMMY_TOKEN = "test-mint-token"


class _NeverOpen:
    def open(self, request, timeout=20):  # noqa: ANN001
        raise AssertionError("token POST must not run")


class _OkResponse:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self) -> bytes:
        return json.dumps({"access_token": _DUMMY_TOKEN, "expires_in": 3600}).encode()


class _Recording200:
    def __init__(self) -> None:
        self.url = ""

    def open(self, request: Request, timeout=20):  # noqa: ANN001
        self.url = request.full_url
        return _OkResponse()


class _ForcedRedirect(BaseHandler):
    def __init__(self, code: int) -> None:
        self.code = code

    def default_open(self, req: Request):
        headers = Message()
        headers["Location"] = "https://evil.example/steal"
        raise HTTPError(req.full_url, self.code, "Found", headers, None)


class MintGuardTests(unittest.TestCase):
    def tearDown(self) -> None:
        clear_token_cache()

    def test_normalize_strips_scheme_slash_and_case(self) -> None:
        raw = f"https://{BUYER.upper()}/"
        self.assertEqual(normalize_shop(raw), BUYER)
        self.assertEqual(normalize_shop(f"http://{DEMO}/admin"), DEMO)

    def test_refused_when_shop_missing(self) -> None:
        env = {"SHOPIFY_CLIENT_ID": _DUMMY_ID, "SHOPIFY_CLIENT_SECRET": _DUMMY_SECRET}
        with self.assertRaises(HelpdeskError) as ctx:
            mint_token(_DUMMY_ID, _DUMMY_SECRET, env=env, opener=_NeverOpen())
        self.assertEqual(ctx.exception.code, "auth_failed")
        self.assertNotIn("access_token", ctx.exception.message)
        self.assertNotIn(_DUMMY_SECRET, ctx.exception.message)
        self.assertNotIn(_DUMMY_TOKEN, json.dumps(ctx.exception.as_json()))
        self.assertFalse(_can_mint(DEMO, env))
        self.assertFalse(_can_mint(BUYER, env))

    def test_refused_when_shop_is_not_myshopify(self) -> None:
        env = {
            "SHOPIFY_SHOP": "https://store.example.com/",
            "SHOPIFY_CLIENT_ID": _DUMMY_ID,
            "SHOPIFY_CLIENT_SECRET": _DUMMY_SECRET,
        }
        with self.assertRaises(HelpdeskError) as ctx:
            mint_token(_DUMMY_ID, _DUMMY_SECRET, env=env, opener=_NeverOpen())
        self.assertEqual(ctx.exception.code, "auth_failed")
        self.assertNotIn(_DUMMY_SECRET, ctx.exception.message)
        self.assertFalse(_can_mint("store.example.com", env))
        self.assertFalse(_can_mint(BUYER, env))

    def test_refused_when_request_shop_does_not_match_env(self) -> None:
        env = {
            "SHOPIFY_SHOP": f"https://{BUYER}/",
            "SHOPIFY_CLIENT_ID": _DUMMY_ID,
            "SHOPIFY_CLIENT_SECRET": _DUMMY_SECRET,
        }
        self.assertTrue(_can_mint(BUYER, env))
        self.assertFalse(_can_mint(DEMO, env))
        self.assertFalse(_can_mint("other-store.myshopify.com", env))
        with self.assertRaises(HelpdeskError) as ctx:
            graphql(
                "other-store.myshopify.com",
                _DUMMY_ID,
                _DUMMY_SECRET,
                "query { shop { name } }",
                env=env,
            )
        self.assertEqual(ctx.exception.code, "auth_failed")
        self.assertNotIn(_DUMMY_SECRET, ctx.exception.message)

    def test_refused_when_token_url_would_redirect(self) -> None:
        env = {
            "SHOPIFY_SHOP": f"https://{BUYER}/",
            "SHOPIFY_CLIENT_ID": _DUMMY_ID,
            "SHOPIFY_CLIENT_SECRET": _DUMMY_SECRET,
        }
        for code in (301, 302):
            opener = build_opener(_RefuseRedirects(), _ForcedRedirect(code))
            with self.assertRaises(HelpdeskError) as ctx:
                mint_token(_DUMMY_ID, _DUMMY_SECRET, env=env, opener=opener)
            self.assertEqual(ctx.exception.code, "auth_failed")
            self.assertNotIn("evil.example", ctx.exception.message)
            self.assertNotIn(_DUMMY_SECRET, ctx.exception.message)
            self.assertNotIn("access_token", ctx.exception.message)

    def test_success_mocks_buyer_shop_200(self) -> None:
        env = {
            "SHOPIFY_SHOP": f"HTTPS://{BUYER.upper()}/",
            "SHOPIFY_CLIENT_ID": _DUMMY_ID,
            "SHOPIFY_CLIENT_SECRET": _DUMMY_SECRET,
        }
        opener = _Recording200()
        token = mint_token(_DUMMY_ID, _DUMMY_SECRET, env=env, opener=opener)
        self.assertEqual(token, _DUMMY_TOKEN)
        self.assertEqual(opener.url, f"https://{BUYER}/admin/oauth/access_token")
        self.assertTrue(_can_mint(BUYER, env))
        self.assertFalse(_can_mint(DEMO, env))
        self.assertEqual(require_configured_shop(env), BUYER)
        self.assertEqual(require_pinned_shop(env), BUYER)

    def test_success_mocks_cute_things_demo_host(self) -> None:
        env = {
            "SHOPIFY_SHOP": f"https://{DEMO}/",
            "SHOPIFY_CLIENT_ID": _DUMMY_ID,
            "SHOPIFY_CLIENT_SECRET": _DUMMY_SECRET,
        }
        opener = _Recording200()
        token = mint_token(_DUMMY_ID, _DUMMY_SECRET, env=env, opener=opener)
        self.assertEqual(token, _DUMMY_TOKEN)
        self.assertEqual(opener.url, f"https://{DEMO}/admin/oauth/access_token")
        self.assertTrue(_can_mint(DEMO, env))
        self.assertFalse(_can_mint(BUYER, env))

    def test_token_opener_uses_refuse_redirect_handler(self) -> None:
        opener = token_opener()
        kinds = {type(handler) for handler in opener.handlers}
        self.assertIn(_RefuseRedirects, kinds)
        handler = next(h for h in opener.handlers if isinstance(h, _RefuseRedirects))
        req = Request(f"https://{BUYER}/admin/oauth/access_token", data=b"{}", method="POST")
        with self.assertRaises(HelpdeskError) as ctx:
            handler.redirect_request(req, None, 302, "Found", {}, "https://evil.example/steal")
        self.assertEqual(ctx.exception.code, "auth_failed")

    def test_join_live_targets_configured_shop(self) -> None:
        env = {
            "SHOPIFY_SHOP": BUYER,
            "SHOPIFY_CLIENT_ID": _DUMMY_ID,
            "SHOPIFY_CLIENT_SECRET": _DUMMY_SECRET,
        }
        seen: dict[str, str] = {}

        def fake_gql(shop: str, *args, **kwargs):  # noqa: ANN002, ANN003
            seen["shop"] = shop
            return {
                "orders": {
                    "nodes": [
                        {
                            "id": "gid://shopify/Order/1",
                            "customer": {"id": "gid://shopify/Customer/1"},
                        }
                    ]
                }
            }

        with (
            patch.object(join_mod, "graphql", fake_gql),
            patch.object(join_mod, "_try_live", lambda shop, _env: object()),
        ):
            found = join_mod._live_order("1001", env)
        self.assertEqual(seen["shop"], BUYER)
        self.assertEqual(found["id"], "gid://shopify/Order/1")
        self.assertEqual(found["customerId"], "gid://shopify/Customer/1")


if __name__ == "__main__":
    unittest.main()
