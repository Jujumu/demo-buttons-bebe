"""The webhook tenant path must not accept another tenant's event."""

from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, patch

import httpx

from bb_webhook import app as app_module


class WebhookTenantMismatchTests(unittest.IsolatedAsyncioTestCase):
    async def test_mismatch_returns_404_before_persistence(self) -> None:
        event = {"tenant_id": "tenant-from-payload"}
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app_module.app),
            base_url="http://demo.test",
        ) as client:
            app_module._rate_window.clear()
            with (
                patch.object(app_module, "verify_signature", lambda *_args: True),
                patch.object(app_module, "parse_event", lambda _raw: event),
            ):
                response = await client.post(
                    "/webhook/gorgias/tenant-from-url",
                    content=b"{}",
                    headers={"Content-Type": "application/json"},
                )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(), {"error": "tenant_not_found"})

    async def test_app_level_replay_checker_patch_remains_effective(self) -> None:
        event = {
            "tenant_id": "demo",
            "ticket_id": 1,
            "message_id": "message-1",
            "event_type": "ticket.message.created",
            "author_type": "customer",
            "is_customer_message": True,
            "channel": "email",
            "created_at": "2026-01-01T00:00:00Z",
        }
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app_module.app),
            base_url="http://demo.test",
        ) as client:
            app_module._rate_window.clear()
            with (
                patch.object(app_module, "verify_signature", lambda *_args: True),
                patch.object(app_module, "parse_event", lambda _raw: event),
                patch.object(app_module, "is_duplicate", AsyncMock(return_value=False)),
                patch.object(app_module, "is_event_too_old", lambda _created: True),
            ):
                response = await client.post(
                    "/webhook/gorgias/demo",
                    content=b"{}",
                )

        self.assertEqual(response.status_code, 410)
        self.assertEqual(response.json(), {"error": "event_expired"})


if __name__ == "__main__":
    unittest.main()
