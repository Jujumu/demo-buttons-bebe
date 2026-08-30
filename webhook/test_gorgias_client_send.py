"""Regression tests for dashboard replies sent through the Gorgias API."""

from __future__ import annotations

import unittest
from unittest.mock import patch

import httpx

from bb_webhook.gorgias_client import GorgiasClient


class _FakeAsyncClient:
    calls: list[tuple[str, str, dict]] = []

    def __init__(self, **kwargs: object) -> None:
        self.options = kwargs

    async def __aenter__(self) -> "_FakeAsyncClient":
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        return None

    async def get(self, url: str, **kwargs: object) -> httpx.Response:
        self.calls.append(("GET", url, kwargs))
        if url.endswith("/api/messages"):
            return httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "id": 44,
                            "from_agent": False,
                            "channel": "email",
                            "source": {
                                "from": {"address": "customer@example.com"},
                                "to": [{"address": "support@example.com"}],
                            },
                            "sender": {"email": "customer@example.com"},
                        }
                    ]
                },
                request=httpx.Request("GET", url),
            )
        if url.endswith("/api/tickets/123/messages/9001"):
            return httpx.Response(
                200,
                json={"id": 9001, "sent_datetime": "2026-08-26T00:00:01Z"},
                request=httpx.Request("GET", url),
            )
        raise AssertionError(f"unexpected GET {url}")

    async def post(self, url: str, **kwargs: object) -> httpx.Response:
        self.calls.append(("POST", url, kwargs))
        return httpx.Response(
            201,
            json={"id": 9001, "sent_datetime": None},
            request=httpx.Request("POST", url),
        )


class GorgiasClientSendTests(unittest.IsolatedAsyncioTestCase):
    async def test_send_public_reply_uses_current_listing_and_confirms_delivery(self) -> None:
        _FakeAsyncClient.calls = []
        with patch("bb_webhook.gorgias_client.httpx.AsyncClient", _FakeAsyncClient):
            result = await GorgiasClient(
                subdomain="helpdesk",
                email="agent@example.com",
                api_key="test-key",
                base_url="https://helpdesk.example.com",
            ).send_public_reply(123, "Your order is on the way.")

        self.assertEqual(result["delivery_status"], "sent")
        self.assertEqual(result["message_id"], 9001)
        self.assertEqual(_FakeAsyncClient.calls[0][1], "https://helpdesk.example.com/api/messages")
        post = next(call for call in _FakeAsyncClient.calls if call[0] == "POST")
        payload = post[2]["json"]
        self.assertEqual(payload["channel"], "email")
        self.assertEqual(payload["via"], "api")
        self.assertEqual(payload["receiver"], {"email": "customer@example.com"})
        self.assertEqual(payload["sender"], {"email": "agent@example.com"})
        self.assertEqual(payload["source"]["from"]["address"], "support@example.com")


if __name__ == "__main__":
    unittest.main()
