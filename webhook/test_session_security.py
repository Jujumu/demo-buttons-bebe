"""Authenticated owner and adversarial proxy tests; no external operations."""
import base64
import hashlib
import hmac
import json
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import httpx
from fastapi import Request
from bb_webhook import app as app_module, database, session_store
from bb_webhook.console_auth import build_session_token, hash_password, safe_next_path
from bb_webhook.routers import auth

ORIGIN = "https://support.buttonsbebe.com"


class SessionSecurityTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "state.sqlite3"
        await database.init_db(self.path)
        await session_store.initialize(self.path)
        self.settings = SimpleNamespace(console_username="chaim", console_password_hash=hash_password("local-test-password"), console_session_secret="local-test-secret", demo_mode=False, db_path_absolute=self.path, gorgias_auth="local-placeholder")
        self.settings_patch = patch.object(app_module, "get_settings", return_value=self.settings)
        self.settings_patch.start()
        self.login_patch = patch.object(auth, "_login_allowed", return_value=True)
        self.login_patch.start()
        self.app = app_module.create_app()

        @self.app.post("/dashboard/api/test-action")
        async def action(request: Request):
            return {"actor_id":request.state.actor_id, "actor_role":request.state.actor_role}

        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app), base_url=ORIGIN)

    async def asyncTearDown(self):
        await self.client.aclose()
        self.login_patch.stop()
        self.settings_patch.stop()
        self.temp.cleanup()

    async def login(self):
        response = await self.client.post("/auth/login", headers={"origin":ORIGIN}, json={"username":"chaim", "password":"local-test-password", "next":"/inbox/?view=all"})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["redirect"], "/inbox/?view=all")
        return response.cookies["bb_console_session"]

    def legacy_token(self):
        def enc(value): return base64.urlsafe_b64encode(value).rstrip(b"=").decode()
        payload = enc(f"chaim\n{int(time.time())+3600}".encode())
        return payload + "." + enc(hmac.new(b"local-test-secret", payload.encode(), hashlib.sha256).digest())

    async def test_registered_session_is_required_and_logout_revokes_copied_cookie(self):
        unknown = build_session_token("chaim", "local-test-secret")
        response = await self.client.get("/auth/session", headers={"cookie":f"bb_console_session={unknown}"})
        self.assertEqual(response.status_code, 401)
        token = await self.login()
        self.assertEqual((await self.client.get("/auth/session")).status_code, 200)
        logout = await self.client.post("/auth/logout", headers={"origin":ORIGIN})
        self.assertEqual(logout.status_code, 200)
        replay = await self.client.get("/auth/session", headers={"cookie":f"bb_console_session={token}"})
        self.assertEqual(replay.status_code, 401)

    async def test_legacy_session_migrates_once_and_cannot_reactivate(self):
        token = self.legacy_token()
        headers = {"cookie":f"bb_console_session={token}"}
        for _ in range(2):
            self.assertEqual((await self.client.get("/auth/session",headers=headers)).status_code,200)
        self.assertEqual((await self.client.post("/auth/logout",headers={**headers,"origin":ORIGIN})).status_code,200)
        for altered in (token, token + "=", token + "!"):
            replay = await self.client.get("/auth/session",headers={"cookie":f"bb_console_session={altered}"})
            self.assertEqual(replay.status_code,401)

    async def test_dashboard_mutations_require_session_and_trusted_origin(self):
        path = "/dashboard/api/test-action"
        self.assertEqual((await self.client.post(path,headers={"origin":ORIGIN})).status_code,401)
        await self.login()
        for headers in ({}, {"origin":"https://evil.invalid"}, {"origin":ORIGIN,"sec-fetch-site":"cross-site"}, {"origin":"null"}):
            self.assertEqual((await self.client.post(path,headers=headers)).status_code,403)
        valid = await self.client.post(path,headers={"origin":ORIGIN})
        self.assertEqual(valid.json(),{"actor_id":"owner:chaim","actor_role":"owner"})

    async def test_login_and_logout_reject_cross_site_requests(self):
        for path in ("/auth/login","/auth/logout"):
            self.assertEqual((await self.client.post(path,headers={"origin":"https://evil.invalid"},json={})).status_code,403)

    async def test_processor_results_are_not_a_public_or_browser_api(self):
        # Direct local producer reaches the handler's normal payload validator.
        self.assertEqual((await self.client.post("/dashboard/api/results",json={})).status_code,400)
        await self.login()
        for headers in ({"x-forwarded-for":"127.0.0.1"}, {"forwarded":"for=127.0.0.1"}, {"origin":ORIGIN}):
            self.assertEqual((await self.client.post("/dashboard/api/results",headers=headers,json={})).status_code,403)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app,client=("203.0.113.5",123)),base_url=ORIGIN) as remote:
            self.assertEqual((await remote.post("/dashboard/api/results",json={})).status_code,403)
            self.assertEqual((await remote.get("/dashboard/api/tickets",headers={"x-forwarded-for":"127.0.0.1","x-authenticated-actor":"owner:chaim"})).status_code,401)

    async def test_forward_auth_uses_original_uri_and_method(self):
        response = await self.client.get("/auth/page-check",headers={"x-forwarded-uri":"/inbox/?view=all", "x-forwarded-method":"GET"})
        self.assertEqual(response.headers["location"],"/console/login?next=%2Finbox%2F%3Fview%3Dall")
        api = await self.client.get("/auth/page-check",headers={"x-forwarded-uri":"/inbox/console/api/helpdesk", "x-forwarded-method":"POST"})
        self.assertEqual(api.status_code,401)
        await self.login()
        self.assertEqual((await self.client.get("/auth/check",headers={"x-forwarded-method":"POST"})).status_code,403)
        self.assertEqual((await self.client.get("/auth/check",headers={"x-forwarded-method":"POST","origin":ORIGIN})).status_code,204)
        self.assertEqual((await self.client.get("/auth/check")).status_code,204)

    async def test_revocation_store_failure_does_not_claim_logout_success(self):
        await self.login()
        with patch.object(session_store,"revoke",side_effect=RuntimeError("database unavailable")):
            result = await self.client.post("/auth/logout",headers={"origin":ORIGIN})
        self.assertEqual(result.status_code,503)
        self.assertNotIn("set-cookie",result.headers)

    async def test_readiness_checks_real_database_and_schema(self):
        result = await self.client.get("/ready")
        self.assertEqual(result.status_code,200,result.text)
        self.assertEqual(result.json()["diagnostics"]["pending_jobs"],0)
        from bb_webhook.db import Database
        await Database(self.path).execute("DROP TABLE parsed_messages")
        self.assertEqual((await self.client.get("/ready")).status_code,503)


class RedirectTests(unittest.TestCase):
    def test_unsafe_paths_are_refused(self):
        for path in ("/console/../../evil", "/inbox/%2e%2e/evil", "/inbox/%252e%252e/evil", "/console/\\evil", "/inbox/%0aevil", "https://evil.invalid", "//evil.invalid", "/inbox.evil/"):
            self.assertEqual(safe_next_path(path),"/console/",path)
        self.assertEqual(safe_next_path("/inbox/?view=all"),"/inbox/?view=all")


if __name__ == "__main__":
    unittest.main()
