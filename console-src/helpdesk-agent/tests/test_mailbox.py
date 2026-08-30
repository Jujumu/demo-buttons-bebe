"""AgentMail pull_mailbox → ingest_email. Fixtures when the live list is down."""

from __future__ import annotations

import json
import os
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
sys.path.insert(0, str(ROOT))

from helpdesk.dispatch import WRITE_TOOLS, dispatch, invoke
from helpdesk.fixtures_intake import ADA_TRACKING, PRIZE_SPAM
from helpdesk.fixtures_live_holes import C_UNFULFILLED, O_1001
from helpdesk.mailbox import handle_pull_mailbox
from helpdesk.mcp_server import handle_rpc
from helpdesk.names import TOOL_NAMES, TOOL_PULL_MAILBOX
from helpdesk.tickets import reset as reset_tickets


class MailboxPullTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_tickets()
        os.environ["SHOPIFY_MUTATIONS_ENABLED"] = "0"
        os.environ.pop("AGENTMAIL_API_KEY", None)

    def test_pull_mailbox_ada_creates_one_ticket_joined_to_1001(self) -> None:
        payload = dispatch(TOOL_PULL_MAILBOX, {"limit": 5})
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["source"], "fixture")
        ada = next(row for row in payload["ingested"] if row["customerName"] == "Ada")
        self.assertEqual(ada["subject"], ADA_TRACKING["subject"])
        self.assertEqual(ada["customerId"], C_UNFULFILLED)
        self.assertEqual(ada["orderId"], O_1001)
        self.assertEqual(ada["status"], "open")
        self.assertNotEqual(ada["status"], "OPEN")
        self.assertNotEqual(ada["customerName"], "Demo Unfulfilled")
        self.assertNotIn("displayName", ada)
        listed = dispatch("helpdesk.list_tickets", {"view": "open", "limit": 20})["tickets"]
        self.assertTrue(any(row["id"] == ada["id"] for row in listed))
        ticket = dispatch("helpdesk.get_ticket", {"ticketId": ada["id"]})["ticket"]
        self.assertEqual(ticket["messages"][0]["body"], ADA_TRACKING["body"])
        self.assertEqual(ticket["messages"][0]["name"], "Ada")

    def test_prize_is_spam_and_not_in_list_tickets(self) -> None:
        payload = dispatch(TOOL_PULL_MAILBOX, {"limit": 5})
        self.assertTrue(any("prize" in row["subject"].lower() for row in payload["spam"]))
        self.assertTrue(any(row["from"] == PRIZE_SPAM["from"] for row in payload["spam"]))
        self.assertFalse(any("prize" in row["subject"].lower() for row in payload["ingested"]))
        listed = dispatch("helpdesk.list_tickets", {"view": "all", "limit": 100})["tickets"]
        self.assertFalse(any("prize" in f"{row['subject']} {row['snippet']}".lower() for row in listed))

    def test_second_pull_of_same_message_id_does_not_duplicate(self) -> None:
        first = dispatch(TOOL_PULL_MAILBOX, {"limit": 5})
        ids = [row["id"] for row in first["ingested"]]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(len(first["ingested"]), 4)
        self.assertEqual(first["skipped"], 0)
        second = dispatch(TOOL_PULL_MAILBOX, {"limit": 5})
        self.assertEqual(second["ingested"], [])
        self.assertEqual(second["spam"], [])
        self.assertEqual(second["skipped"], 5)
        listed = dispatch("helpdesk.list_tickets", {"view": "open", "limit": 100})["tickets"]
        pulled = [row for row in listed if row["id"].startswith("t-in-")]
        self.assertEqual(len(pulled), 4)

    def test_no_agentmail_api_key_value_in_repo(self) -> None:
        skip_dirs = {".git", "node_modules", ".venv", "venv", "__pycache__", "output", ".cursor"}
        self.assertTrue((REPO / "console-src" / "helpdesk-agent").is_dir())
        for path in REPO.rglob("*"):
            if any(part in skip_dirs for part in path.parts):
                continue
            if not path.is_file():
                continue
            if path.suffix.lower() not in {
                ".py", ".js", ".md", ".html", ".css", ".json", ".yml", ".yaml",
                ".txt", ".example", ".env",
            } and path.name not in {".env.example", "env.example"}:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            for line in text.splitlines():
                stripped = line.strip()
                if stripped.startswith("#"):
                    continue
                if stripped.startswith("export "):
                    stripped = stripped[7:].strip()
                if stripped.startswith("AGENTMAIL_API_KEY="):
                    value = stripped.split("=", 1)[1].strip().strip("\"'")
                    self.assertEqual(value, "", f"{path} must not commit a key")

    def test_mutations_still_refused(self) -> None:
        for tool in WRITE_TOOLS:
            payload = invoke(tool, {"ticketId": "t-in-1"})
            self.assertFalse(payload["ok"])
            self.assertEqual(payload["error"], "forbidden")
        self.assertIn(TOOL_PULL_MAILBOX, TOOL_NAMES)
        self.assertNotIn(TOOL_PULL_MAILBOX, WRITE_TOOLS)

    def test_mailbox_module_is_pull_only(self) -> None:
        src = (ROOT / "helpdesk" / "mailbox.py").read_text(encoding="utf-8")
        self.assertNotIn(".send(", src)
        self.assertNotIn(".reply(", src)
        self.assertNotIn(".forward(", src)
        self.assertNotIn(".create(", src)
        self.assertNotIn(".delete(", src)
        self.assertNotIn("inboxes.create", src)
        self.assertNotIn("print(", src)
        blob = json.dumps(handle_pull_mailbox({"limit": 1}))
        self.assertNotIn("AGENTMAIL_API_KEY", blob)
        self.assertNotIn("am-", blob)

    def test_mcp_lists_pull_mailbox(self) -> None:
        reply = handle_rpc({"jsonrpc": "2.0", "id": 12, "method": "tools/list"})
        names = [tool["name"] for tool in reply["result"]["tools"]]
        self.assertEqual(names, list(TOOL_NAMES))
        self.assertEqual(len(names), 13)
        self.assertIn(TOOL_PULL_MAILBOX, names)

    def test_unjoined_fixtures_stay_gid_null(self) -> None:
        payload = dispatch(TOOL_PULL_MAILBOX, {"limit": 5})
        by_name = {row["customerName"]: row for row in payload["ingested"]}
        for name in ("Sam", "Priya", "Jordan"):
            self.assertIsNone(by_name[name]["customerId"], name)
            self.assertIsNone(by_name[name]["orderId"], name)
            self.assertEqual(by_name[name]["status"], "open")


if __name__ == "__main__":
    unittest.main()
