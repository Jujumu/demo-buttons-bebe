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
        self.assertIn("t-ada-track", [row["id"] for row in mine])
        self.assertEqual(mine[0]["id"], "t-ada-track")
        for row in mine:
            self.assertEqual(row["status"], "open")
            self.assertNotEqual(row["status"], "OPEN")
        closed = dispatch("helpdesk.list_tickets", {"view": "closed", "limit": 20})["tickets"]
        self.assertIn("t-ada-closed", [row["id"] for row in closed])
        self.assertEqual(closed[0]["id"], "t-ada-closed")
        for row in closed:
            self.assertEqual(row["status"], "closed")
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
        inbound = ticket["messages"][0]
        self.assertEqual(inbound["from"], "customer")
        self.assertEqual(inbound["fromName"], "Ada Demo")
        self.assertEqual(inbound["name"], "Ada Demo")
        self.assertNotEqual(inbound["fromName"].lower(), "teddyjubu")
        agent = ticket["messages"][1]
        self.assertEqual(agent["from"], "agent")
        self.assertEqual(agent["fromName"], "Demo Shop")
        self.assertNotEqual(agent["fromName"], inbound["fromName"])

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
            self.assertIn("refund", payload["details"]["refused"])
            self.assertIn("cancel", payload["details"]["refused"])
            self.assertFalse(payload["details"]["mutationsEnabled"])

    def test_escalate_ticket_is_first_party_not_shopify(self) -> None:
        from unittest.mock import patch

        before = dispatch("helpdesk.get_ticket", {"ticketId": "t-ada-track"})["ticket"]
        self.assertFalse(before.get("escalated"))
        with patch("helpdesk.client.graphql") as gql:
            payload = dispatch(
                "helpdesk.escalate_ticket",
                {"ticketId": "t-ada-track", "reason": "pending review"},
            )
            gql.assert_not_called()
        self.assertTrue(payload["ok"])
        ticket = payload["ticket"]
        self.assertTrue(ticket["escalated"])
        self.assertEqual(ticket["status"], "open")
        self.assertEqual(ticket["escalationReason"], "pending review")
        self.assertTrue(any("escalated" in (event.get("note") or "") for event in ticket["statusEvents"]))
        again = dispatch("helpdesk.get_ticket", {"ticketId": "t-ada-track"})["ticket"]
        self.assertTrue(again["escalated"])
        rows = dispatch("helpdesk.list_tickets", {"view": "open", "limit": 20})["tickets"]
        ada = next(row for row in rows if row["id"] == "t-ada-track")
        self.assertNotIn("escalated", ada)
        self.assertEqual(ada["status"], "open")
        self.assertNotIn("helpdesk.escalate_ticket", WRITE_TOOLS)

    def test_unsubscribe_fixture_surfaces_request_type(self) -> None:
        rows = dispatch("helpdesk.list_tickets", {"view": "open", "limit": 20})["tickets"]
        priya = next(row for row in rows if row["id"] == "t-priya-unsub")
        self.assertEqual(priya["requestType"], "marketing_unsubscribe")
        self.assertEqual(priya["customerName"], "Priya Lane")
        self.assertEqual(priya["status"], "open")
        ada = next(row for row in rows if row["id"] == "t-ada-track")
        self.assertIsNone(ada["requestType"])
        casey = next(row for row in rows if row["id"] == "t-casey-visor")
        self.assertIsNone(casey["requestType"])
        ticket = dispatch("helpdesk.get_ticket", {"ticketId": "t-priya-unsub"})["ticket"]
        self.assertEqual(ticket["requestType"], "marketing_unsubscribe")
        self.assertEqual(ticket["status"], "open")
        self.assertFalse(ticket.get("escalated"))
        from helpdesk.queries import CUSTOMER_QUERY, ORDER_QUERY

        self.assertNotIn("emailMarketingConsent", CUSTOMER_QUERY)
        self.assertNotIn("marketingUnsubscribe", CUSTOMER_QUERY + ORDER_QUERY)
        self.assertNotIn("customerEmailMarketingConsentUpdate", CUSTOMER_QUERY)
        self.assertEqual(WRITE_TOOLS, frozenset({"helpdesk.send", "helpdesk.refund", "helpdesk.cancel"}))
        self.assertNotIn("helpdesk.mark_request_type", WRITE_TOOLS)

    def test_privacy_fixture_surfaces_request_type(self) -> None:
        rows = dispatch("helpdesk.list_tickets", {"view": "open", "limit": 20})["tickets"]
        lee = next(row for row in rows if row["id"] == "t-lee-privacy")
        self.assertEqual(lee["requestType"], "privacy_request")
        self.assertEqual(lee["customerName"], "Lee Chen")
        self.assertEqual(lee["status"], "open")
        priya = next(row for row in rows if row["id"] == "t-priya-unsub")
        self.assertEqual(priya["requestType"], "marketing_unsubscribe")
        ada = next(row for row in rows if row["id"] == "t-ada-track")
        self.assertIsNone(ada["requestType"])
        casey = next(row for row in rows if row["id"] == "t-casey-visor")
        self.assertIsNone(casey["requestType"])
        ticket = dispatch("helpdesk.get_ticket", {"ticketId": "t-lee-privacy"})["ticket"]
        self.assertEqual(ticket["requestType"], "privacy_request")
        self.assertEqual(ticket["privacySubtype"], "delete")
        self.assertFalse(ticket["privacyHandled"])
        self.assertEqual(ticket["status"], "open")
        self.assertFalse(ticket.get("escalated"))
        from helpdesk.queries import CUSTOMER_QUERY, ORDER_QUERY
        from helpdesk.tickets import mark_privacy_handled
        from unittest.mock import patch

        handled = mark_privacy_handled("t-lee-privacy")
        self.assertTrue(handled["privacyHandled"])
        with patch("helpdesk.client.graphql") as gql:
            again = mark_privacy_handled("t-lee-privacy")
            gql.assert_not_called()
        self.assertTrue(again["privacyHandled"])
        blob = CUSTOMER_QUERY + ORDER_QUERY
        self.assertNotIn("customerPrivacy", blob)
        self.assertNotIn("customerRequestDataErasure", blob)
        self.assertNotIn("customerRedact", blob)
        self.assertNotIn("dataRequest", blob)
        self.assertNotIn("gdpr", blob.lower())
        self.assertEqual(WRITE_TOOLS, frozenset({"helpdesk.send", "helpdesk.refund", "helpdesk.cancel"}))
        self.assertNotIn("helpdesk.mark_request_type", WRITE_TOOLS)
        self.assertNotIn("helpdesk.privacy_request", WRITE_TOOLS)
        self.assertNotIn("helpdesk.mark_privacy_handled", WRITE_TOOLS)

    def test_write_gate_status_reports_refused_money_writes(self) -> None:
        os.environ["SHOPIFY_MUTATIONS_ENABLED"] = "0"
        payload = dispatch("helpdesk.write_gate_status", {})
        self.assertTrue(payload["ok"])
        self.assertFalse(payload["mutationsEnabled"])
        self.assertEqual(payload["refused"], ["send", "refund", "cancel"])
        self.assertIn("helpdesk.refund", payload["tools"])
        self.assertIn("helpdesk.cancel", payload["tools"])
        self.assertIn("SHOPIFY_MUTATIONS_ENABLED stays 0", payload["message"])


if __name__ == "__main__":
    unittest.main()
