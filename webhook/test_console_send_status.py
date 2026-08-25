"""The dashboard must expose Gorgias delivery state instead of hiding it."""

from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, Mock, patch

import httpx

from bb_webhook import app as app_module


class _FakeGorgiasClient:
    def __init__(self, result: dict) -> None:
        self.result = result

    async def send_public_reply(self, ticket_id: int, text: str) -> dict:
        return self.result


class ConsoleSendStatusTests(unittest.IsolatedAsyncioTestCase):
    async def _post(self, result: dict) -> httpx.Response:
        fake = _FakeGorgiasClient(result)
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app_module.app),
            base_url="http://demo.test",
        ) as client:
            with (
                patch.object(app_module, "dashboard_ticket_exists", AsyncMock(return_value=True)),
                patch.object(app_module, "_GClient", return_value=fake),
                patch.object(app_module, "_record_lesson", Mock()),
            ):
                return await client.post(
                    "/dashboard/api/ticket/1/send",
                    json={"text": "Thanks!", "confirmed": True},
                )

    async def test_confirmed_sent_reply_returns_delivery_confirmation(self) -> None:
        response = await self._post(
            {"ok": True, "delivery_status": "sent", "message_id": 9001}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"ok": True, "delivery_status": "sent", "message_id": 9001},
        )

    async def test_pending_reply_is_not_labelled_sent(self) -> None:
        response = await self._post(
            {"ok": True, "delivery_status": "pending", "message_id": 9002}
        )
        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json()["delivery_status"], "pending")


if __name__ == "__main__":
    unittest.main()
