"""The console HTTP door must share invoke() with MCP/CLI."""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HELPDESK = ROOT / "console-src" / "helpdesk-agent"
sys.path.insert(0, str(HELPDESK))
sys.path.insert(0, str(ROOT / "webhook" / "src"))

from helpdesk.dispatch import dispatch, invoke
from helpdesk.fixtures_sample import ADA, ORDER_ADA
from helpdesk.http import handle_http
from helpdesk.names import SAMPLE_SHOP, TOOL_NAMES

from bb_webhook.helpdesk_door import handle_tool, helpdesk_root


class HelpdeskDoorTests(unittest.TestCase):
    def test_http_matches_dispatch_for_all_ten_tools(self) -> None:
        cases = [
            ("helpdesk.list_tickets", {"view": "open", "limit": 5}),
            ("helpdesk.get_ticket", {"ticketId": "1001"}),
            ("helpdesk.get_customer", {"shop": SAMPLE_SHOP, "customerId": ADA}),
            ("helpdesk.get_order", {"shop": SAMPLE_SHOP, "orderId": ORDER_ADA}),
            ("helpdesk.get_returns", {"shop": SAMPLE_SHOP, "orderId": ORDER_ADA}),
            ("helpdesk.list_past_orders", {"shop": SAMPLE_SHOP, "customerId": ADA}),
            ("helpdesk.draft_reply", {"ticketId": "1001", "shop": SAMPLE_SHOP}),
            ("helpdesk.summarize_thread", {"ticketId": "1001"}),
            ("helpdesk.search_macros", {"query": "shipping"}),
            ("helpdesk.apply_macro", {"macroId": "shipping-delay", "mode": "replace"}),
        ]
        for tool, args in cases:
            handled = dispatch(tool, args)
            http_payload = handle_http(tool, args)
            door = handle_tool(tool, args)
            self.assertEqual(handled, http_payload, tool)
            self.assertEqual(handled, door, tool)
            self.assertTrue(handled["ok"], tool)

    def test_writes_are_forbidden(self) -> None:
        for tool in ("helpdesk.send", "helpdesk.refund", "helpdesk.cancel"):
            payload = handle_tool(tool, {})
            self.assertFalse(payload["ok"])
            self.assertEqual(payload["error"], "forbidden")
            self.assertNotIn("Traceback", str(payload))

    def test_payload_has_no_token_keys(self) -> None:
        payload = handle_tool(
            "helpdesk.get_customer",
            {"shop": SAMPLE_SHOP, "customerId": ADA},
        )
        blob = str(payload).lower()
        self.assertNotIn("shpat_", blob)
        self.assertNotIn("client_secret", blob)
        self.assertNotIn("access_token", blob)
        self.assertEqual(tuple(TOOL_NAMES), TOOL_NAMES)

    def test_unknown_tool_is_structured(self) -> None:
        payload = invoke("helpdesk.send", {})
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"], "forbidden")

    def test_composer_tools_are_text_not_writes(self) -> None:
        draft = handle_tool("helpdesk.draft_reply", {"ticketId": "1001", "shop": SAMPLE_SHOP})
        self.assertTrue(draft["ok"])
        self.assertIn("draft", draft)
        summary = handle_tool("helpdesk.summarize_thread", {"ticketId": "1001"})
        self.assertTrue(summary["ok"])
        self.assertIn("summary", summary)
        found = handle_tool("helpdesk.search_macros", {"query": "shipping"})
        self.assertTrue(found["ok"])
        self.assertGreaterEqual(len(found["macros"]), 1)
        applied = handle_tool("helpdesk.apply_macro", {"macroId": "shipping-delay", "mode": "replace"})
        self.assertTrue(applied["ok"])
        self.assertIn("text", applied)
        self.assertNotIn("sent", applied)

    def test_helpdesk_root_points_at_the_organ(self) -> None:
        root = helpdesk_root()
        self.assertTrue((root / "helpdesk" / "dispatch.py").is_file())
        self.assertTrue((root / "helpdesk" / "http.py").is_file())

    def test_console_route_returns_the_same_json(self) -> None:
        try:
            import httpx
            from bb_webhook import app as app_module
        except ImportError:
            self.skipTest("fastapi/httpx not installed in this interpreter")

        expected = handle_tool(
            "helpdesk.get_customer",
            {"shop": SAMPLE_SHOP, "customerId": ADA},
        )
        with httpx.Client(
            transport=httpx.ASGITransport(app=app_module.app),
            base_url="http://demo.test",
        ) as client:
            response = client.post(
                "/dashboard/api/helpdesk",
                json={
                    "tool": "helpdesk.get_customer",
                    "arguments": {"shop": SAMPLE_SHOP, "customerId": ADA},
                },
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), expected)


if __name__ == "__main__":
    os.environ.setdefault("HELPDESK_SOURCE", "sample")
    unittest.main()
