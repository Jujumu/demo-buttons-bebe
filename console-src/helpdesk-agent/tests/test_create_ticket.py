"""First-party empty compose ticket. No Shopify join."""

from __future__ import annotations

import io
import json
import unittest
from contextlib import redirect_stdout
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from helpdesk.cli import main as cli_main
from helpdesk.dispatch import dispatch
from helpdesk.names import TOOL_CREATE_TICKET, TOOL_NAMES
from helpdesk.tickets import reset as reset_tickets


class CreateTicketTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_tickets()

    def test_create_ticket_is_empty_first_party(self) -> None:
        payload = dispatch(TOOL_CREATE_TICKET, {})
        self.assertTrue(payload["ok"])
        ticket = payload["ticket"]
        self.assertTrue(str(ticket["id"]).startswith("t-in-"))
        self.assertEqual(ticket["customerName"], "New ticket")
        self.assertEqual(ticket["subject"], "New ticket")
        self.assertEqual(ticket["snippet"], "")
        self.assertEqual(ticket["status"], "open")
        self.assertEqual(ticket["messages"], [])
        self.assertIsNone(ticket["customerId"])
        self.assertIsNone(ticket["orderId"])
        self.assertEqual(ticket["source"], "compose")
        self.assertEqual(ticket["assignee"], "me")
        self.assertEqual(ticket["requestType"], None)

    def test_create_ticket_lists_in_all_and_skips_shopify_gids(self) -> None:
        created = dispatch(TOOL_CREATE_TICKET, {})["ticket"]
        listed = dispatch("helpdesk.list_tickets", {"view": "all", "limit": 50})
        ids = [row["id"] for row in listed["tickets"]]
        self.assertIn(created["id"], ids)
        row = next(row for row in listed["tickets"] if row["id"] == created["id"])
        self.assertIsNone(row["customerId"])
        self.assertIsNone(row["orderId"])

    def test_create_ticket_draft_is_empty(self) -> None:
        created = dispatch(TOOL_CREATE_TICKET, {})["ticket"]
        draft = dispatch("helpdesk.draft_reply", {"ticketId": created["id"]})
        self.assertEqual(draft["draft"], "")

    def test_cli_create_ticket_matches_dispatch(self) -> None:
        handled = dispatch(TOOL_CREATE_TICKET, {})
        reset_tickets()
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = cli_main(["create-ticket"])
        cli = json.loads(buf.getvalue())
        self.assertEqual(code, 0)
        self.assertEqual(handled["ticket"]["source"], "compose")
        self.assertEqual(cli["ticket"]["source"], "compose")
        self.assertEqual(cli["ticket"]["messages"], [])
        self.assertIsNone(cli["ticket"]["customerId"])

    def test_tool_is_registered(self) -> None:
        self.assertIn(TOOL_CREATE_TICKET, TOOL_NAMES)
        self.assertEqual(len(TOOL_NAMES), 19)


if __name__ == "__main__":
    unittest.main()
