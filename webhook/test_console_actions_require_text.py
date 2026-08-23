"""Console send/note actions reject empty text before any external write."""

from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, patch

import httpx

from bb_webhook import app as app_module


class ConsoleActionsRequireTextTests(unittest.IsolatedAsyncioTestCase):
    async def test_send_and_note_reject_empty_text_with_400(self) -> None:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app_module.app),
            base_url="http://demo.test",
        ) as client:
            with patch.object(
                app_module,
                "dashboard_ticket_exists",
                AsyncMock(return_value=True),
            ):
                send = await client.post(
                    "/dashboard/api/ticket/1/send",
                    json={"text": "   ", "confirmed": True},
                )
                note = await client.post(
                    "/dashboard/api/ticket/1/note",
                    json={"text": ""},
                )

        self.assertEqual(send.status_code, 400)
        self.assertEqual(send.json(), {"error": "empty reply"})
        self.assertEqual(note.status_code, 400)
        self.assertEqual(note.json(), {"error": "empty note"})


if __name__ == "__main__":
    unittest.main()
