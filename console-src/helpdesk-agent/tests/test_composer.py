from __future__ import annotations

import json
import os
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from helpdesk.dispatch import WRITE_TOOLS, dispatch, invoke
from helpdesk.fixtures_sample import ADA, ORDER_ADA
from helpdesk.mcp_server import handle_rpc
from helpdesk.names import SAMPLE_SHOP, TOOL_NAMES


FORBIDDEN_DRAFT = (
    "gorgias",
    "malky",
    "rivky",
    "sperber",
    "morgenstern",
    "ai-demo-unfulfilled@example.com",
    "refund you",
    "i cancelled",
    "i refunded",
)


class ComposerTissueTests(unittest.TestCase):
    def test_draft_reply_is_text_not_a_write(self) -> None:
        payload = dispatch("helpdesk.draft_reply", {"ticketId": "1001", "shop": SAMPLE_SHOP})
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["source"], "fixture")
        self.assertIn("draft", payload)
        self.assertIsInstance(payload["draft"], str)
        self.assertGreater(len(payload["draft"]), 20)
        self.assertIn("Ada", payload["draft"])
        self.assertIn("#9001", payload["draft"])
        blob = payload["draft"].lower()
        for snippet in FORBIDDEN_DRAFT:
            self.assertNotIn(snippet, blob, snippet)
        self.assertNotIn("helpdesk.draft_reply", WRITE_TOOLS)

    def test_summarize_thread_is_a_mute_peek(self) -> None:
        payload = dispatch("helpdesk.summarize_thread", {"ticketId": "1001"})
        self.assertTrue(payload["ok"])
        self.assertIn("summary", payload)
        self.assertNotIn("draft", payload)
        self.assertIn("Ada", payload["summary"])
        self.assertIn("Open", payload["summary"])
        self.assertNotIn("OPEN", payload["summary"])
        self.assertNotIn("helpdesk.summarize_thread", WRITE_TOOLS)

    def test_already_loaded_thread_does_not_need_sample_id(self) -> None:
        thread = {
            "id": "t-ada-track",
            "subject": "Tracking on order #1001 has not moved",
            "status": "open",
            "customerName": "Ada Demo",
            "messages": [
                {
                    "id": "m1",
                    "fromAgent": False,
                    "name": "Ada Demo",
                    "body": "Where is my order #1001?",
                    "at": "2026-08-28T14:02:00Z",
                }
            ],
        }
        order = {
            "name": "#1001",
            "displayFinancialStatus": "PAID",
            "displayFulfillmentStatus": "FULFILLED",
            "fulfillments": [{"trackingInfo": [{"number": "DEMO-1001", "company": "Demo Carrier"}]}],
        }
        draft = dispatch(
            "helpdesk.draft_reply",
            {
                "ticketId": "t-ada-track",
                "shop": SAMPLE_SHOP,
                "thread": thread,
                "customer": {"displayName": "Ada Demo"},
                "order": order,
            },
        )
        self.assertTrue(draft["ok"])
        self.assertIn("#1001", draft["draft"])
        self.assertIn("DEMO-1001", draft["draft"])
        summary = dispatch("helpdesk.summarize_thread", {"ticketId": "t-ada-track", "thread": thread})
        self.assertTrue(summary["ok"])
        self.assertIn("Ada", summary["summary"])

    def test_writes_stay_forbidden(self) -> None:
        os.environ["SHOPIFY_MUTATIONS_ENABLED"] = "0"
        for tool in ("helpdesk.send", "helpdesk.refund", "helpdesk.cancel"):
            payload = invoke(tool, {"ticketId": "1001"})
            self.assertFalse(payload["ok"])
            self.assertEqual(payload["error"], "forbidden")
            self.assertIn("SHOPIFY_MUTATIONS_ENABLED stays 0", payload["message"])

    def test_mcp_lists_composer_tools(self) -> None:
        reply = handle_rpc({"jsonrpc": "2.0", "id": 9, "method": "tools/list"})
        names = [tool["name"] for tool in reply["result"]["tools"]]
        self.assertEqual(names, list(TOOL_NAMES))
        self.assertEqual(len(names), 10)
        self.assertIn("helpdesk.search_macros", names)
        self.assertIn("helpdesk.apply_macro", names)

    def test_unknown_inbox_ticket_without_thread_is_not_found(self) -> None:
        payload = invoke("helpdesk.draft_reply", {"ticketId": "t-missing"})
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"], "not_found")

    def test_payload_has_no_token_or_gorgias_keys(self) -> None:
        payload = dispatch(
            "helpdesk.draft_reply",
            {"ticketId": "1001", "shop": SAMPLE_SHOP, "customerId": ADA, "orderId": ORDER_ADA},
        )
        blob = json.dumps(payload).lower()
        self.assertNotIn("shpat_", blob)
        self.assertNotIn("gorgias", blob)
        self.assertNotIn("client_secret", blob)


if __name__ == "__main__":
    unittest.main()
