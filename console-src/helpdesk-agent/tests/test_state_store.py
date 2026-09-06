"""Failure and restart tests use invented local records, never production data."""
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import subprocess
import sys
import unittest
from unittest.mock import patch
from helpdesk import tickets, state_store


class StateStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "inbox.sqlite3"
        self.legacy = Path(self.tmp.name) / "tickets.json"
        self.env = patch.dict(os.environ, {"HELPDESK_PRODUCTION": "1", "HELPDESK_DB_FILE": str(self.db), "HELPDESK_STORE_FILE": str(self.legacy), "HELPDESK_SEEN_FILE": ""})
        self.env.start()
        tickets.reset()

    def tearDown(self):
        self.env.stop()
        tickets.reset()
        self.tmp.cleanup()

    def add(self):
        return tickets.add_ticket(customer_name="Local test", subject="Privacy request", body="Delete my data", received_at="2026-09-07T00:00:00Z", customer_id=None, order_id=None, channel="email", from_email=None, dedupe_key=("test", "1"))

    def test_flags_survive_restart(self):
        row = self.add()
        tickets.escalate_ticket(row["id"], "Manual review")
        tickets.mark_privacy_handled(row["id"])
        tickets.reset()
        loaded = tickets.get_ticket(row["id"])
        self.assertTrue(loaded["escalated"])
        self.assertTrue(loaded["privacyHandled"])

    def test_ticket_seen_and_sequence_roll_back_together(self):
        with self.assertRaises(RuntimeError):
            with tickets.transaction():
                tickets.remember_intake({"messageId": "test-1", "source": "agentmail"})
                self.add()
                raise RuntimeError("Interrupted operation")
        tickets.reset()
        self.assertFalse(tickets.seen_message_id("test-1"))
        self.assertEqual(tickets.list_tickets("all"), [])
        self.assertEqual(self.add()["id"], "t-in-1")

    def test_committed_dedupe_and_ticket_survive_restart(self):
        with tickets.transaction():
            tickets.remember_intake({"messageId": "test-1", "source": "agentmail"})
            row = self.add()
        tickets.reset()
        self.assertTrue(tickets.seen_message_id("test-1"))
        self.assertEqual(self.add()["id"], row["id"])
        self.assertEqual(len(tickets.list_tickets("all")), 1)

    def test_database_corruption_is_visible(self):
        self.add()
        with sqlite3.connect(self.db) as db:
            db.execute("UPDATE inbox_state SET payload='invalid json'")
        with self.assertRaises(state_store.StoreUnavailable):
            tickets.reset()
        with sqlite3.connect(self.db) as db:
            self.assertEqual(db.execute("SELECT payload FROM inbox_state").fetchone()[0], "invalid json")

    def test_legacy_corruption_is_not_empty_success(self):
        self.legacy.write_text("broken json")
        with self.assertRaises(state_store.StoreUnavailable):
            tickets.reset()
        self.assertEqual(self.legacy.read_text(), "broken json")

    def test_legacy_migration_retains_original(self):
        row = {"id": "t-in-90", "customerName": "Local fixture", "subject": "Existing", "snippet": "Existing", "status": "open", "updatedAt": "2026-09-01T00:00:00Z", "messages": [], "statusEvents": []}
        payload = json.dumps({"tickets": [row], "dedupe": [], "nextSeq": 91})
        self.legacy.write_text(payload)
        with tickets.transaction():
            pass
        self.legacy.write_text("Later legacy file must not override SQLite")
        tickets.reset()
        self.assertEqual(tickets.list_tickets("all")[0]["id"], "t-in-90")

    def test_failed_commit_does_not_leave_success_in_memory(self):
        with patch.object(state_store, "write", side_effect=sqlite3.OperationalError("disk full")):
            with self.assertRaises(sqlite3.OperationalError):
                self.add()
        self.assertEqual(tickets.list_tickets("all"), [])

    def test_multiple_processes_do_not_overwrite_each_other(self):
        code = """
import sys
sys.path.insert(0, sys.argv[1])
from helpdesk import tickets
tickets.add_ticket(customer_name='Local test', subject='Test', body='Test', received_at='2026-09-07T00:00:00Z', customer_id=None, order_id=None, channel='email', from_email=None, dedupe_key=('concurrency',sys.argv[2]))
"""
        processes = [subprocess.Popen([sys.executable, "-c", code, str(Path(tickets.__file__).parent.parent), str(i)], stdout=subprocess.PIPE, stderr=subprocess.PIPE) for i in range(4)]
        for process in processes:
            out, err = process.communicate(timeout=20)
            self.assertEqual(process.returncode, 0, err.decode())
        tickets.reset()
        self.assertEqual({row["id"] for row in tickets.list_tickets("all")}, {"t-in-1", "t-in-2", "t-in-3", "t-in-4"})

    def test_reads_do_not_rewrite_state_or_take_writer_lock(self):
        from helpdesk.dispatch import invoke
        self.add()
        with sqlite3.connect(self.db, isolation_level=None) as writer:
            writer.execute("BEGIN IMMEDIATE")
            with patch.object(state_store, "write", side_effect=AssertionError("read must not write")):
                result = invoke("helpdesk.list_tickets", {"view":"all"})
                self.assertEqual(len(result["tickets"]),1)
            writer.rollback()

    def test_read_only_operation_refuses_nested_mutation(self):
        self.add()
        with tickets.transaction(write=False):
            with self.assertRaises(state_store.StoreUnavailable):
                tickets.escalate_ticket("t-in-1")
        self.assertFalse(tickets.get_ticket("t-in-1")["escalated"])
