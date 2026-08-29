"""HTTP tests for the workspace organ facade."""

from __future__ import annotations

import json
import unittest
from starlette.requests import Request

from bb_webhook.routers import workspace as workspace_routes


def request_for(method: str, path: str, body: dict | None = None) -> Request:
    raw = b"" if body is None else json.dumps(body).encode()
    sent = False

    async def receive():
        nonlocal sent
        if sent:
            return {"type": "http.disconnect"}
        sent = True
        return {"type": "http.request", "body": raw, "more_body": False}

    return Request(
        {
            "type": "http",
            "method": method,
            "path": path,
            "query_string": b"",
            "headers": [(b"content-type", b"application/json")],
            "client": ("127.0.0.1", 12345),
            "scheme": "https",
        },
        receive,
    )


class WorkspaceApiTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        workspace_routes.reset_workspace_fixtures()

    async def test_inbox_uses_fixture_tickets_only(self) -> None:
        response = await workspace_routes.workspace_inbox(view="open")
        payload = json.loads(response.body)
        self.assertEqual(payload["source"], "fixture")
        self.assertNotIn("shopify_shop", payload)
        names = {ticket["customer_name"] for ticket in payload["tickets"]}
        self.assertIn("AI-DEMO Customer A", names)
        self.assertNotIn("Malky Sperber", names)

    async def test_ticket_workspace_keeps_thread_when_shopify_errors(self) -> None:
        response = await workspace_routes.workspace_ticket("tk-1003")
        payload = json.loads(response.body)
        self.assertEqual(payload["thread"]["status"], "ok")
        self.assertEqual(payload["shopify"]["status"], "error")
        retry = await workspace_routes.workspace_ticket("tk-1003", retry_shopify=True)
        retried = json.loads(retry.body)
        self.assertEqual(retried["shopify"]["status"], "empty")
        self.assertEqual(retried["thread"]["status"], "ok")

    async def test_draft_insert_does_not_send(self) -> None:
        response = await workspace_routes.workspace_draft_insert("tk-1001")
        payload = json.loads(response.body)
        self.assertFalse(payload["sent"])
        self.assertEqual(payload["draft"]["status"], "ok")

    async def test_send_rejects_empty_body(self) -> None:
        response = await workspace_routes.workspace_send(
            "tk-1001",
            request_for("POST", "/dashboard/api/workspace/tickets/tk-1001/send", {"body": ""}),
        )
        self.assertEqual(response.status_code, 400)
        payload = json.loads(response.body)
        self.assertEqual(payload["status"], "error")

    async def test_human_send_records_reply_without_autosend_flag(self) -> None:
        response = await workspace_routes.workspace_send(
            "tk-1002",
            request_for(
                "POST",
                "/dashboard/api/workspace/tickets/tk-1002/send",
                {"body": "Order #1002 is fulfilled. Use the Track link.", "close": False},
            ),
        )
        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.body)
        self.assertTrue(payload["sent"])
        self.assertFalse(payload["auto_sent"])

    async def test_unknown_ticket_is_not_found(self) -> None:
        response = await workspace_routes.workspace_ticket("tk-missing")
        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
