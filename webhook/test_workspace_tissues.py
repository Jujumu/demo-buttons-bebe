"""Contract tests for Team Support Workspace tissues."""

from __future__ import annotations

import ast
import unittest
from pathlib import Path

from bb_webhook.tissues import drafts, identity, returns, shopify_context, tickets, workspace
from bb_webhook.tissues.types import (
    CUSTOMER_RAIL_FIELDS,
    ORDER_RAIL_FIELDS,
    RAIL_LOCK_QUERY,
    TissueResult,
)

TISSUE_DIR = Path(__file__).resolve().parent / "src" / "bb_webhook" / "tissues"
INBOX = Path(__file__).resolve().parents[1] / "console-src" / "inbox.html"
FORBIDDEN_PII = (
    "Malky",
    "Sperber",
    "Gaia",
    "gorgias.com",
)


class TissueIsolationTests(unittest.TestCase):
    def setUp(self) -> None:
        tickets.reset_fixtures()
        shopify_context.reset_fixtures()
        drafts.reset_fixtures()

    def test_ticket_tissue_does_not_import_other_tissues(self) -> None:
        siblings = {"tickets", "identity", "shopify_context", "returns", "drafts", "workspace"}
        for name in ("tickets", "identity", "shopify_context", "returns", "drafts"):
            tree = ast.parse((TISSUE_DIR / f"{name}.py").read_text(encoding="utf-8"))
            imported = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.level >= 1 and node.module:
                    imported.add(node.module.split(".")[-1])
            self.assertTrue(
                imported.isdisjoint(siblings),
                msg=f"{name} imported sibling tissues {imported & siblings}",
            )

    def test_workspace_composes_public_modules_only(self) -> None:
        source = (TISSUE_DIR / "workspace.py").read_text(encoding="utf-8")
        self.assertIn("from . import drafts, identity, returns, shopify_context, tickets", source)
        self.assertNotIn("._", source)

    def test_shopify_error_does_not_block_thread(self) -> None:
        thread = tickets.get_thread("tk-1003")
        shopify = shopify_context.get_order_context("tk-1003")
        composed = workspace.open_ticket("tk-1003")

        self.assertEqual(thread.status, "ok")
        self.assertEqual(shopify.status, "error")
        self.assertEqual(composed.status, "ok")
        self.assertEqual(composed.data.thread.status, "ok")
        self.assertEqual(composed.data.shopify.status, "error")
        self.assertGreaterEqual(composed.data.thread.data.message_count, 1)

    def test_shopify_retry_is_local_and_can_degrade_to_empty(self) -> None:
        first = shopify_context.get_order_context("tk-1003")
        retried = shopify_context.retry_order_context("tk-1003")
        self.assertEqual(first.status, "error")
        self.assertEqual(retried.status, "empty")
        self.assertIn("conversation still works", retried.empty_reason or "")

    def test_returns_degrade_when_empty(self) -> None:
        empty = returns.get_return_context("tk-1001")
        also_empty = returns.get_return_context("tk-1004")
        self.assertEqual(empty.status, "empty")
        self.assertEqual(also_empty.status, "empty")
        self.assertEqual(empty.data.returnStatus, "NO_RETURN")
        self.assertEqual(empty.data.returns.nodes, ())

    def test_identity_unidentified_ticket_is_empty_not_guessed(self) -> None:
        result = identity.get_identity("tk-1006")
        self.assertEqual(result.status, "empty")
        self.assertIn("No customer is linked", result.empty_reason or "")

    def test_draft_insert_and_discard_never_send(self) -> None:
        inserted = workspace.insert_draft("tk-1001")
        discarded = workspace.discard_draft("tk-1001")
        self.assertFalse(inserted["sent"])
        self.assertFalse(discarded["sent"])
        self.assertEqual(inserted["action"], "insert")
        self.assertEqual(discarded["action"], "discard")
        self.assertEqual(drafts.get_draft("tk-1001").status, "empty")

    def test_send_requires_body_and_is_human_gated(self) -> None:
        blank = workspace.send_reply("tk-1002", "   ")
        self.assertEqual(blank.status, "error")
        sent = workspace.send_reply("tk-1002", "Order #1002 is fulfilled. Use the Track link.")
        self.assertEqual(sent.status, "ok")
        self.assertEqual(sent.data.messages[-1].kind, "agent")
        self.assertEqual(tickets.get_ticket("tk-1002").status, "open")

    def test_send_and_close_updates_ticket_status(self) -> None:
        result = workspace.send_reply("tk-1001", "Tracking is on the order card.", close=True)
        self.assertEqual(result.status, "ok")
        self.assertEqual(tickets.get_ticket("tk-1001").status, "closed")
        self.assertEqual(result.data.messages[-1].kind, "status")

    def test_inbox_views_and_fixture_names_are_fake(self) -> None:
        snapshot = workspace.inbox("open")
        names = {ticket.customer_name for ticket in snapshot.tickets}
        self.assertIn("AI-DEMO Customer A", names)
        self.assertIn("AI-DEMO Customer B", names)
        self.assertEqual(snapshot.source, "fixture")
        blob = "\n".join(ticket.as_dict().__repr__() for ticket in snapshot.tickets)
        for banned in FORBIDDEN_PII:
            self.assertNotIn(banned, blob)

    def test_shopify_dto_has_no_mutation_actions(self) -> None:
        order = shopify_context.get_order_context("tk-1002").data
        payload = order.as_dict()
        for banned in ("edit", "refund", "cancel", "Edit", "Refund", "Cancel"):
            self.assertNotIn(banned, payload)
        track = payload["fulfillments"][0]["trackingInfo"][0]
        self.assertEqual(track["number"], "AI-DEMO-1002")
        self.assertTrue(track["url"].startswith("https://example.com/"))

    def test_identity_uses_locked_customer_fields(self) -> None:
        payload = identity.get_identity("tk-1002").data.as_dict()
        self.assertEqual(set(payload), set(CUSTOMER_RAIL_FIELDS))
        self.assertNotIn("email", payload)
        self.assertEqual(payload["displayName"], "AI-DEMO Customer A")
        self.assertEqual(payload["defaultEmailAddress"]["emailAddress"], "ai-demo-a@example.com")
        self.assertEqual(payload["defaultEmailAddress"].keys(), {"emailAddress"})

    def test_order_dto_matches_admin_graphql_lock_and_sandbox_shape(self) -> None:
        paid = {
            shopify_context.get_order_context("tk-1002").data.name,
            shopify_context.get_order_context("tk-1001").data.name,
            shopify_context.get_order_context("tk-1004").data.name,
        }
        self.assertEqual(paid, {"#1002", "#1003", "#1004"})
        for ticket_id in ("tk-1001", "tk-1002", "tk-1004"):
            payload = shopify_context.get_order_context(ticket_id).data.as_dict()
            self.assertEqual(set(payload), set(ORDER_RAIL_FIELDS))
            self.assertEqual(payload["displayFinancialStatus"], "PAID")
            self.assertEqual(payload["returnStatus"], "NO_RETURN")
            self.assertEqual(payload["returns"]["nodes"], [])
            for node in payload["lineItems"]["nodes"]:
                self.assertIsNone(node["sku"])
        self.assertIsNone(shopify_context.get_order_context("tk-1002").data.billingAddress)
        self.assertIsNone(shopify_context.get_order_context("tk-1001").data.billingAddress)
        self.assertIsNotNone(shopify_context.get_order_context("tk-1004").data.billingAddress)
        self.assertIn("defaultEmailAddress { emailAddress }", RAIL_LOCK_QUERY)
        self.assertNotIn("Customer.email", RAIL_LOCK_QUERY)

    def test_open_ticket_returns_tissue_envelopes(self) -> None:
        result = workspace.open_ticket("tk-1001")
        self.assertIsInstance(result, TissueResult)
        payload = result.data.as_dict()
        for key in ("thread", "identity", "shopify", "returns", "draft", "past_orders"):
            self.assertIn(payload[key]["status"], {"ok", "empty", "error", "unavailable"})


class InboxSourceGuardTests(unittest.TestCase):
    def test_inbox_html_follows_ui_lock_and_avoids_gorgias_pii(self) -> None:
        source = INBOX.read_text(encoding="utf-8")
        self.assertIn("grid-template-columns:200px 300px minmax(0,1fr) 300px", source)
        self.assertIn("--ground:#F4F0EA", source)
        self.assertIn("--surface:#FFFDF9", source)
        self.assertIn("--ink:#1C1916", source)
        self.assertIn("--mute:#5C564F", source)
        self.assertIn("--accent:#B5471D", source)
        self.assertIn("IBM Plex Sans", source)
        self.assertIn("IBM Plex Mono", source)
        self.assertIn("Skip to thread", source)
        self.assertIn("outline:var(--focus)", source)
        self.assertIn("prefers-reduced-motion", source)
        self.assertIn(">Insert<", source)
        self.assertIn(">Discard<", source)
        self.assertIn("Send &amp; close", source)
        self.assertNotIn("Inter", source)
        self.assertNotIn("indigo", source.lower())
        self.assertNotIn("purple", source.lower())
        self.assertNotIn("Gaia", source)
        for banned in FORBIDDEN_PII:
            self.assertNotIn(banned, source)
        strip = source.split("draft-strip", 2)[1]
        self.assertNotIn(">Send<", strip)
        self.assertIn("This order", source)
        self.assertIn("Past orders", source)
        self.assertIn("defaultEmailAddress", source)
        self.assertIn("No SKU", source)
        self.assertIn('"No "+label+"."', source)
        self.assertIn('addrBlock("billingAddress"', source)
        self.assertIn("returnStatus", source)
        self.assertNotIn("ident.data.email", source)
        self.assertNotIn("order_number", source)
        self.assertNotIn("display_name", source)
        self.assertNotIn("Edit order", source)
        self.assertNotIn(">Refund</", source)
        self.assertNotIn("id=\"refund\"", source)
        self.assertNotIn("Cancel order", source)
        self.assertNotIn("yznyc1-ez", source)
        self.assertNotIn("Cute Things", source)
        self.assertNotIn("SHOPIFY_CLIENT", source)

    def test_tissues_never_call_a_live_shop(self) -> None:
        blob = "\n".join(path.read_text(encoding="utf-8") for path in TISSUE_DIR.glob("*.py"))
        for banned in ("yznyc1-ez", "Cute Things", "api.getredo.com", "myshopify.com", "SHOPIFY_CLIENT"):
            self.assertNotIn(banned, blob)


if __name__ == "__main__":
    unittest.main()
