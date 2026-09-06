"""Inbound From is the customer persona, not the mailbox login."""

from __future__ import annotations

import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from helpdesk.speakers import (
    inbound_from_name,
    is_mailbox_email,
    is_mailbox_name,
    project_customer_name,
    project_message,
)


class SpeakerTests(unittest.TestCase):
    def test_mailbox_email_is_shop_login(self) -> None:
        self.assertTrue(is_mailbox_email("teddyjubu@agentmail.to"))
        self.assertTrue(is_mailbox_email("helpdesk-support@agentmail.to"))
        self.assertFalse(is_mailbox_email("ada.tracking@example.com"))
        self.assertFalse(is_mailbox_email("sam.rattle@example.com"))

    def test_persona_name_is_not_mailbox(self) -> None:
        self.assertFalse(is_mailbox_name("Pat Rivera", "teddyjubu@agentmail.to"))
        self.assertFalse(is_mailbox_name("Ada Demo", "ada.tracking@example.com"))
        self.assertTrue(is_mailbox_name("teddyjubu", "teddyjubu@agentmail.to"))
        self.assertTrue(is_mailbox_name("teddyjubu@agentmail.to", "teddyjubu@agentmail.to"))

    def test_inbound_prefers_from_name_then_ticket_customer(self) -> None:
        ticket = {"customerName": "Ada Demo", "fromEmail": "ada.tracking@example.com"}
        message = {"from": "customer", "fromAgent": False, "name": "teddyjubu"}
        name, email = inbound_from_name(ticket, message)
        self.assertEqual(name, "Ada Demo")
        self.assertEqual(email, "ada.tracking@example.com")

    def test_agent_message_stays_shop_identity(self) -> None:
        ticket = {"customerName": "Ada Demo"}
        message = {"from": "agent", "fromAgent": True, "name": "Demo Shop"}
        projected = project_message(ticket, message)
        self.assertEqual(projected["from"], "agent")
        self.assertEqual(projected["fromName"], "Demo Shop")
        self.assertNotEqual(projected["fromName"], "Ada Demo")

    def test_list_row_prefers_customer_name_over_mailbox(self) -> None:
        ticket = {
            "customerName": "teddyjubu",
            "fromEmail": "teddyjubu@agentmail.to",
            "messages": [
                {
                    "from": "customer",
                    "fromAgent": False,
                    "fromName": "Sam",
                    "name": "Sam",
                    "fromEmail": "sam.rattle@example.com",
                }
            ],
        }
        self.assertEqual(project_customer_name(ticket), "Sam")
