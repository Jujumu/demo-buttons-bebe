from __future__ import annotations

import json
import unittest
from email.message import Message
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import BaseHandler, Request, build_opener
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from helpdesk.auth import (
    PINNED_LIVE_SHOP,
    _RefuseRedirects,
    clear_token_cache,
    mint_token,
    normalize_shop,
    require_pinned_shop,
    token_opener,
)
from helpdesk.errors import HelpdeskError
from helpdesk.shop import _can_mint

PINNED = PINNED_LIVE_SHOP
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
        raw = f"https://{PINNED.upper()}/"
        self.assertEqual(normalize_shop(raw), PINNED)
        self.assertEqual(normalize_shop(f"http://{PINNED}/admin"), PINNED)

    def test_refused_when_shop_missing(self) -> None:
        env = {"SHOPIFY_CLIENT_ID": _DUMMY_ID, "SHOPIFY_CLIENT_SECRET": _DUMMY_SECRET}
        with self.assertRaises(HelpdeskError) as ctx:
            mint_token(_DUMMY_ID, _DUMMY_SECRET, env=env, opener=_NeverOpen())
        self.assertEqual(ctx.exception.code, "auth_failed")
        self.assertNotIn("access_token", ctx.exception.message)
        self.assertNotIn(_DUMMY_SECRET, ctx.exception.message)
        self.assertNotIn(_DUMMY_TOKEN, json.dumps(ctx.exception.as_json()))
        self.assertFalse(_can_mint(PINNED, env))

    def test_refused_when_shop_is_another_host(self) -> None:
        env = {
            "SHOPIFY_SHOP": "https://other-store.myshopify.com/",
            "SHOPIFY_CLIENT_ID": _DUMMY_ID,
            "SHOPIFY_CLIENT_SECRET": _DUMMY_SECRET,
        }
        with self.assertRaises(HelpdeskError) as ctx:
            mint_token(_DUMMY_ID, _DUMMY_SECRET, env=env, opener=_NeverOpen())
        self.assertEqual(ctx.exception.code, "auth_failed")
        self.assertNotIn(_DUMMY_SECRET, ctx.exception.message)
        self.assertFalse(_can_mint("other-store.myshopify.com", env))
        self.assertFalse(_can_mint(PINNED, env))

    def test_refused_when_token_url_would_redirect(self) -> None:
        env = {
            "SHOPIFY_SHOP": f"https://{PINNED}/",
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

    def test_success_mocks_same_host_200(self) -> None:
        env = {
            "SHOPIFY_SHOP": f"HTTPS://{PINNED.upper()}/",
            "SHOPIFY_CLIENT_ID": _DUMMY_ID,
            "SHOPIFY_CLIENT_SECRET": _DUMMY_SECRET,
        }
        opener = _Recording200()
        token = mint_token(_DUMMY_ID, _DUMMY_SECRET, env=env, opener=opener)
        self.assertEqual(token, _DUMMY_TOKEN)
        self.assertEqual(opener.url, f"https://{PINNED}/admin/oauth/access_token")
        self.assertTrue(_can_mint(PINNED, env))
        self.assertEqual(require_pinned_shop(env), PINNED)

    def test_token_opener_uses_refuse_redirect_handler(self) -> None:
        opener = token_opener()
        kinds = {type(handler) for handler in opener.handlers}
        self.assertIn(_RefuseRedirects, kinds)
        handler = next(h for h in opener.handlers if isinstance(h, _RefuseRedirects))
        req = Request(f"https://{PINNED}/admin/oauth/access_token", data=b"{}", method="POST")
        with self.assertRaises(HelpdeskError) as ctx:
            handler.redirect_request(req, None, 302, "Found", {}, "https://evil.example/steal")
        self.assertEqual(ctx.exception.code, "auth_failed")


if __name__ == "__main__":
    unittest.main()
