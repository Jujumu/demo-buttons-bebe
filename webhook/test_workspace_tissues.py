"""Contract tests for Team Support Workspace tissues."""

from __future__ import annotations

import ast
import unittest
from pathlib import Path

from bb_webhook.tissues import drafts, identity, returns, shopify_context, tickets, workspace
from bb_webhook.tissues.types import TissueResult

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
        active = returns.get_return_context("tk-1004")
        self.assertEqual(empty.status, "empty")
        self.assertEqual(active.status, "ok")
        self.assertTrue(active.data.in_progress)

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
        sent = workspace.send_reply("tk-1002", "The romper on order 1002 is 3 months.")
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
        self.assertIn("Jane Example", names)
        self.assertIn("Alex Patron", names)
        self.assertEqual(snapshot.source, "fixture")
        blob = "\n".join(ticket.as_dict().__repr__() for ticket in snapshot.tickets)
        for banned in FORBIDDEN_PII:
            self.assertNotIn(banned, blob)

    def test_shopify_dto_has_no_mutation_actions(self) -> None:
        order = shopify_context.get_order_context("tk-1001").data
        payload = order.as_dict()
        for banned in ("edit", "refund", "cancel", "Edit", "Refund", "Cancel"):
            self.assertNotIn(banned, payload)
        self.assertEqual(payload["shipment"]["tracking_label"], "Track shipment")
        self.assertTrue(payload["shipment"]["tracking_url"].startswith("https://example.com/"))

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
