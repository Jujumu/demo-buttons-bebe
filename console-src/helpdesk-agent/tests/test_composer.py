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
        self.assertIn("#1001", payload["draft"])
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

    def test_draft_uses_ticket_customer_name_not_display_name(self) -> None:
        from helpdesk.fixtures_intake import ADA_TRACKING
        from helpdesk.tickets import reset as reset_tickets

        reset_tickets()
        ingested = dispatch("helpdesk.ingest_email", ADA_TRACKING)
        self.assertTrue(ingested["ok"])
        self.assertEqual(ingested["customerName"], "Ada")
        payload = dispatch(
            "helpdesk.draft_reply",
            {
                "ticketId": ingested["id"],
                "thread": {
                    "id": ingested["id"],
                    "customerName": "Ada",
                    "status": "open",
                    "subject": ADA_TRACKING["subject"],
                    "messages": [
                        {
                            "fromAgent": False,
                            "name": "Ada",
                            "body": ADA_TRACKING["body"],
                        }
                    ],
                },
                "customer": {"displayName": "Demo Unfulfilled"},
                "order": {
                    "name": "#1001",
                    "displayFinancialStatus": "PAID",
                    "displayFulfillmentStatus": "UNFULFILLED",
                },
            },
        )
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["source"], "fixture")
        self.assertIn("Hi Ada", payload["draft"])
        self.assertIn("#1001", payload["draft"])
        self.assertNotIn("Demo Unfulfilled", payload["draft"])
        self.assertNotIn("Hi Demo", payload["draft"])
        blob = payload["draft"].lower()
        for snippet in FORBIDDEN_DRAFT:
            self.assertNotIn(snippet, blob, snippet)

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
        self.assertEqual(names[: len(TOOL_NAMES)], list(TOOL_NAMES))
        self.assertEqual(len(TOOL_NAMES), 15)
        self.assertIn("helpdesk.search_macros", names)
        self.assertIn("helpdesk.apply_macro", names)
        self.assertIn("helpdesk.ingest_email", names)
        self.assertIn("helpdesk.ingest_chat", names)
        self.assertIn("helpdesk.pull_mailbox", names)

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

    def test_scenario_drafts_match_caduceus_tone(self) -> None:
        """Six seeded demos get useful scenario language; no refund/cancel/send promises."""
        cases = (
            (
                "t-demo-04-return",
                ("Priya", "#1003", "merino throw", "prepaid label", "return portal"),
            ),
            (
                "t-demo-05-cancel",
                ("Eli", "#1001", "wrong size", "will not cancel", "teammate"),
            ),
            (
                "t-demo-08-canada",
                ("Luc", "Montreal", "Muslin Swaddle", "customs", "$35"),
            ),
            (
                "t-demo-14-duplicate",
                ("Drew", "#1001", "bank", "pending authorization", "will not refund"),
            ),
            (
                "t-demo-18-exchange",
                ("Taylor", "#1003", "Bath Towel Hood", "exchange", "will not issue a refund"),
            ),
            (
                "t-demo-22-policy",
                ("Reese", "7 days", "store credit", "Final-sale", "will not process a refund"),
            ),
            (
                "t-demo-03-damaged-rattle",
                ("Sam", "photo", "damage", "order number", "will not refund"),
            ),
            (
                "t-demo-17-plush",
                ("Jamie", "photo", "damage", "order number", "will not refund"),
            ),
        )
        cancel_forbidden = (
            "i cancelled",
            "i refunded",
            "i will cancel your",
            "i will refund",
            "cancel it for you",
            "refund you",
            "i sent",
            "i have sent",
        )
        for ticket_id, keywords in cases:
            with self.subTest(ticket_id=ticket_id):
                payload = dispatch("helpdesk.draft_reply", {"ticketId": ticket_id, "shop": SAMPLE_SHOP})
                self.assertTrue(payload["ok"], ticket_id)
                self.assertEqual(payload["source"], "fixture")
                draft = payload["draft"]
                self.assertIsInstance(draft, str)
                self.assertGreater(len(draft), 40)
                lower = draft.lower()
                for keyword in keywords:
                    self.assertIn(keyword.lower(), lower, f"{ticket_id}: missing {keyword!r}")
                for snippet in FORBIDDEN_DRAFT:
                    self.assertNotIn(snippet, lower, f"{ticket_id}: forbidden {snippet!r}")
                if ticket_id in {"t-demo-03-damaged-rattle", "t-demo-17-plush"}:
                    self.assertNotIn("destination", lower, ticket_id)
                    self.assertNotIn("published catalog", lower, ticket_id)
                if ticket_id == "t-demo-05-cancel":
                    self.assertIn("paid", lower)
                    self.assertIn("unfulfilled", lower)
                    for snippet in cancel_forbidden:
                        self.assertNotIn(snippet, lower, f"cancel ticket: {snippet!r}")
                    self.assertIn("i will not cancel or refund", lower)

    def test_unsubscribe_draft_confirms_opt_out_and_skips_order_invent(self) -> None:
        from helpdesk.tickets import reset as reset_tickets

        reset_tickets()
        payload = dispatch("helpdesk.draft_reply", {"ticketId": "t-priya-unsub"})
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["source"], "fixture")
        draft = payload["draft"]
        lower = draft.lower()
        self.assertIn("Hi Priya", draft)
        self.assertIn("marketing unsubscribe", lower)
        self.assertIn("preference", lower)
        self.assertIn("out of band", lower)
        for snippet in (
            "destination",
            "published catalog",
            "i looked at",
            "handed to a carrier",
            "#1001",
            "#1002",
            "tracking",
            "fulfilled",
        ):
            self.assertNotIn(snippet, lower, snippet)
        for snippet in FORBIDDEN_DRAFT:
            self.assertNotIn(snippet, lower, snippet)
        self.assertNotIn("helpdesk.send", draft)

        invented = dispatch(
            "helpdesk.draft_reply",
            {
                "ticketId": "t-priya-unsub",
                "thread": {
                    "id": "t-priya-unsub",
                    "customerName": "Priya Lane",
                    "status": "open",
                    "requestType": "marketing_unsubscribe",
                    "subject": "Please unsubscribe me from marketing emails",
                    "messages": [
                        {
                            "fromAgent": False,
                            "name": "Priya Lane",
                            "body": "Please take me off the marketing list.",
                        }
                    ],
                },
                "order": {
                    "name": "#1001",
                    "displayFinancialStatus": "PAID",
                    "displayFulfillmentStatus": "FULFILLED",
                    "fulfillments": [{"trackingInfo": [{"number": "DEMO-1001", "company": "Demo Carrier"}]}],
                },
            },
        )
        blob = invented["draft"].lower()
        self.assertIn("marketing unsubscribe", blob)
        self.assertNotIn("#1001", invented["draft"])
        self.assertNotIn("demo-1001", blob)
        self.assertNotIn("destination", blob)
        self.assertNotIn("published catalog", blob)

    def test_privacy_draft_explains_path_and_skips_order_invent(self) -> None:
        from helpdesk.tickets import reset as reset_tickets

        reset_tickets()
        payload = dispatch("helpdesk.draft_reply", {"ticketId": "t-lee-privacy"})
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["source"], "fixture")
        draft = payload["draft"]
        lower = draft.lower()
        self.assertIn("Hi Lee", draft)
        self.assertIn("privacy request", lower)
        self.assertIn("out of band", lower)
        self.assertTrue("export" in lower or "deletion" in lower)
        for snippet in (
            "destination",
            "published catalog",
            "i looked at",
            "handed to a carrier",
            "#1001",
            "#1002",
            "tracking",
            "fulfilled",
        ):
            self.assertNotIn(snippet, lower, snippet)
        for snippet in FORBIDDEN_DRAFT:
            self.assertNotIn(snippet, lower, snippet)

        invented = dispatch(
            "helpdesk.draft_reply",
            {
                "ticketId": "t-lee-privacy",
                "thread": {
                    "id": "t-lee-privacy",
                    "customerName": "Lee Chen",
                    "status": "open",
                    "requestType": "privacy_request",
                    "subject": "GDPR request — please delete my data",
                    "messages": [
                        {
                            "fromAgent": False,
                            "name": "Lee Chen",
                            "body": "Please delete my stored personal data.",
                        }
                    ],
                },
                "order": {
                    "name": "#1001",
                    "displayFinancialStatus": "PAID",
                    "displayFulfillmentStatus": "UNFULFILLED",
                },
            },
        )
        blob = invented["draft"].lower()
        self.assertIn("privacy request", blob)
        self.assertNotIn("#1001", invented["draft"])
        self.assertNotIn("destination", blob)
        self.assertNotIn("published catalog", blob)

    def test_bug_draft_asks_for_device_and_skips_order_invent(self) -> None:
        bug = dispatch(
            "helpdesk.draft_reply",
            {
                "ticketId": "t-bug",
                "thread": {
                    "id": "t-bug",
                    "customerName": "Ada Demo",
                    "status": "open",
                    "requestType": "bug",
                    "subject": "Checkout crash on iOS",
                    "messages": [{"fromAgent": False, "name": "Ada Demo", "body": "The app crashes on checkout."}],
                },
                "order": {
                    "name": "#1001",
                    "displayFinancialStatus": "PAID",
                    "displayFulfillmentStatus": "FULFILLED",
                },
            },
        )
        self.assertTrue(bug["ok"])
        self.assertEqual(bug["source"], "fixture")
        draft = bug["draft"]
        lower = draft.lower()
        self.assertIn("Hi Ada", draft)
        self.assertIn("bug report", lower)
        self.assertIn("device", lower)
        self.assertTrue("ios" in lower or "android" in lower)
        for snippet in (
            "destination",
            "published catalog",
            "i looked at",
            "handed to a carrier",
            "#1001",
            "tracking",
            "fulfilled",
        ):
            self.assertNotIn(snippet, lower, snippet)
        for snippet in FORBIDDEN_DRAFT:
            self.assertNotIn(snippet, lower, snippet)

    def test_null_request_type_keeps_existing_draft(self) -> None:
        payload = dispatch("helpdesk.draft_reply", {"ticketId": "1001", "shop": SAMPLE_SHOP})
        self.assertTrue(payload["ok"])
        self.assertIn("#1001", payload["draft"])
        self.assertIn("Ada", payload["draft"])
        self.assertNotIn("bug report", payload["draft"].lower())
        self.assertNotIn("privacy request", payload["draft"].lower())
        self.assertNotIn("marketing unsubscribe", payload["draft"].lower())


if __name__ == "__main__":
    unittest.main()
