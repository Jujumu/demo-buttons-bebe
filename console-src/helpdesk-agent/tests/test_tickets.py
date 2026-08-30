"""Clerk ticket contract: first-party names, GIDs, status events."""

from __future__ import annotations

import os
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from helpdesk.dispatch import WRITE_TOOLS, dispatch, invoke
from helpdesk.fixtures_live_holes import C_FULFILLED, C_UNFULFILLED, O_1001, O_1002
from helpdesk.fixtures_sample import ADA, ORDER_ADA
from helpdesk.names import SAMPLE_SHOP
from helpdesk.tickets import reset as reset_tickets


class TicketContractTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_tickets()

    def test_list_tickets_rows_include_gids(self) -> None:
        payload = dispatch("helpdesk.list_tickets", {"view": "open", "limit": 20})
        self.assertTrue(payload["ok"])
        rows = payload["tickets"]
        self.assertGreaterEqual(len(rows), 1)
        ada = next(row for row in rows if row["id"] == "t-ada-track")
        self.assertEqual(ada["customerName"], "Ada Demo")
        self.assertNotIn("displayName", ada)
        self.assertEqual(ada["customerId"], ADA)
        self.assertEqual(ada["orderId"], ORDER_ADA)
        self.assertTrue(str(ada["customerId"]).startswith("gid://shopify/Customer/"))
        self.assertTrue(str(ada["orderId"]).startswith("gid://shopify/Order/"))
        self.assertEqual(ada["status"], "open")
        self.assertNotEqual(ada["status"], "OPEN")
        for row in rows:
            self.assertIn(row["status"], ("open", "closed", "snoozed"))
            self.assertNotEqual(row["status"], "OPEN")
            self.assertNotIn("displayName", row)

    def test_list_tickets_inbox_views(self) -> None:
        mine = dispatch("helpdesk.list_tickets", {"view": "mine", "limit": 20})["tickets"]
        self.assertEqual([row["id"] for row in mine], ["t-ada-track"])
        closed = dispatch("helpdesk.list_tickets", {"view": "closed", "limit": 20})["tickets"]
        self.assertEqual([row["id"] for row in closed], ["t-ada-closed"])
        snoozed = dispatch("helpdesk.list_tickets", {"view": "snoozed", "limit": 20})["tickets"]
        self.assertEqual(snoozed[0]["status"], "snoozed")
        self.assertIsNone(snoozed[0]["orderId"])

    def test_get_ticket_returns_messages_and_status_events(self) -> None:
        payload = dispatch("helpdesk.get_ticket", {"ticketId": "1001"})
        self.assertTrue(payload["ok"])
        ticket = payload["ticket"]
        self.assertEqual(ticket["id"], "t-ada-track")
        self.assertEqual(ticket["customerName"], "Ada Demo")
        self.assertNotIn("displayName", ticket)
        self.assertEqual(ticket["customerId"], ADA)
        self.assertEqual(ticket["orderId"], ORDER_ADA)
        self.assertGreaterEqual(len(ticket["messages"]), 1)
        self.assertGreaterEqual(len(ticket["statusEvents"]), 1)
        self.assertEqual(ticket["status"], "open")
        self.assertNotEqual(ticket["status"], "OPEN")
        self.assertEqual(ticket["statusEvents"][0]["status"], "open")

    def test_closed_ada_has_a_closed_status_event(self) -> None:
        ticket = dispatch("helpdesk.get_ticket", {"ticketId": "t-ada-closed"})["ticket"]
        self.assertEqual(ticket["status"], "closed")
        self.assertNotEqual(ticket["status"], "OPEN")
        self.assertEqual(ticket["statusEvents"][-1]["status"], "closed")
        self.assertEqual(ticket["statusEvents"][-1]["at"], "2026-08-25T18:12:00Z")

    def test_live_holes_attach_cute_things_gids(self) -> None:
        previous = os.environ.get("HELPDESK_SOURCE")
        os.environ["HELPDESK_SOURCE"] = "live-holes"
        try:
            row = dispatch("helpdesk.list_tickets", {"view": "mine", "limit": 5})["tickets"][0]
            self.assertEqual(row["customerId"], C_UNFULFILLED)
            self.assertEqual(row["orderId"], O_1001)
            ticket = dispatch("helpdesk.get_ticket", {"ticketId": "t-ada-track"})["ticket"]
            self.assertEqual(ticket["customerId"], C_UNFULFILLED)
            self.assertEqual(ticket["orderId"], O_1001)
        finally:
            if previous is None:
                os.environ.pop("HELPDESK_SOURCE", None)
            else:
                os.environ["HELPDESK_SOURCE"] = previous

    def test_live_holes_closed_ada_joins_unfulfilled_1001(self) -> None:
        previous = os.environ.get("HELPDESK_SOURCE")
        os.environ["HELPDESK_SOURCE"] = "live-holes"
        try:
            closed = dispatch("helpdesk.get_ticket", {"ticketId": "t-ada-closed"})["ticket"]
            self.assertEqual(closed["customerId"], C_UNFULFILLED)
            self.assertEqual(closed["orderId"], O_1001)
            self.assertNotEqual(closed["customerId"], C_FULFILLED)
            self.assertNotEqual(closed["orderId"], O_1002)
            self.assertEqual(closed["status"], "closed")
            self.assertEqual(closed["customerName"], "Ada Demo")
            self.assertNotIn("displayName", closed)
            self.assertIn("#1001", closed["subject"] + closed["snippet"])
            jordan = dispatch("helpdesk.get_ticket", {"ticketId": "t-jordan-ship"})["ticket"]
            self.assertIsNone(jordan["orderId"])
            self.assertEqual(jordan["status"], "snoozed")
        finally:
            if previous is None:
                os.environ.pop("HELPDESK_SOURCE", None)
            else:
                os.environ["HELPDESK_SOURCE"] = previous

    def test_customer_name_is_not_display_name(self) -> None:
        ticket = dispatch("helpdesk.get_ticket", {"ticketId": "t-ada-track"})["ticket"]
        customer = dispatch("helpdesk.get_customer", {"shop": SAMPLE_SHOP, "customerId": ADA})["customer"]
        self.assertIn("customerName", ticket)
        self.assertNotIn("displayName", ticket)
        self.assertIn("displayName", customer)
        self.assertNotIn("customerName", customer)
        self.assertEqual(ticket["customerName"], "Ada Demo")
        self.assertEqual(customer["displayName"], "Ada Demo")

    def test_ticket_status_is_not_return_status(self) -> None:
        ticket = dispatch("helpdesk.get_ticket", {"ticketId": "t-ada-track"})["ticket"]
        returns = dispatch("helpdesk.get_returns", {"shop": SAMPLE_SHOP, "orderId": ORDER_ADA})
        self.assertEqual(ticket["status"], "open")
        self.assertEqual(returns["returns"]["nodes"][0]["status"], "OPEN")
        self.assertNotEqual(ticket["status"], returns["returns"]["nodes"][0]["status"])
        self.assertNotEqual(ticket["status"], returns["orderReturnStatus"])

    def test_mutations_refused(self) -> None:
        os.environ["SHOPIFY_MUTATIONS_ENABLED"] = "0"
        for tool in WRITE_TOOLS:
            payload = invoke(tool, {"ticketId": "t-ada-track"})
            self.assertFalse(payload["ok"])
            self.assertEqual(payload["error"], "forbidden")
            self.assertIn("SHOPIFY_MUTATIONS_ENABLED stays 0", payload["message"])


if __name__ == "__main__":
    unittest.main()
