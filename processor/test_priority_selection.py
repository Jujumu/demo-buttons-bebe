"""Bounded sensitive-ticket priority selection over the pending-job window."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import asyncio

import orchestrator
from bb_webhook import database
from bb_webhook.db import Database


def asyncio_run(coroutine):
    return asyncio.run(coroutine)


class PrioritySelectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "queue.db"
        asyncio_run(database.init_db(self.path))
        self.addCleanup(orchestrator._classification_cache.clear)

    def _enqueue(
        self,
        message_id: str,
        *,
        subject: str,
        text: str,
        created_at: str | None = None,
    ) -> int:
        job_id = asyncio_run(database.enqueue_job(
            tenant_id="test",
            ticket_id=100,
            message_id=message_id,
            event_type="ticket.message.created",
            author_type="customer",
            is_customer_message=True,
            payload={
                "message_id": message_id,
                "ticket_subject": subject,
                "message_text": text,
                "ticket_id": 100,
                "intents": [],
            },
            db_path=self.path,
        ))
        if created_at is not None:
            asyncio_run(Database(self.path).execute(
                "UPDATE job_queue SET created_at = ? WHERE message_id = ?",
                (created_at, message_id),
                operation="test_set_created_at",
            ))
        return job_id

    def _window(self):
        return asyncio_run(database.get_pending_job_window(db_path=self.path))

    def test_sensitive_newer_job_is_selected_before_older_normal_jobs(self):
        self._enqueue("normal-one", subject="Order status", text="Where is my order?", created_at="2026-01-01T00:00:00+00:00")
        self._enqueue("normal-two", subject="Sizing question", text="What size should I get?", created_at="2026-01-01T00:01:00+00:00")
        self._enqueue("sensitive-new", subject="Chargeback", text="I will dispute this charge with my bank", created_at="2026-01-01T00:02:00+00:00")

        selected = orchestrator._select_next_job(self._window())

        self.assertEqual(selected["message_id"], "sensitive-new")

    def test_window_bound_prevents_unbounded_reordering(self):
        # Window is ordered oldest-first; a sensitive job placed beyond the
        # 25-job bound cannot jump ahead of the normal backlog head.
        for index in range(26):
            self._enqueue(
                f"normal-{index}",
                subject="Order status",
                text="Where is my order?",
                created_at=f"2026-01-01T00:00:{index:02d}+00:00",
            )
        self._enqueue("sensitive-outside", subject="Chargeback", text="I will dispute this charge", created_at="2026-01-01T01:00:00+00:00")

        window = self._window()
        self.assertEqual(len(window), 25)
        selected = orchestrator._select_next_job(window)

        self.assertEqual(selected["message_id"], "normal-0")
        self.assertNotIn("sensitive-outside", [job["message_id"] for job in window])

    def test_agent_jobs_stay_behind_customer_jobs(self):
        # Enqueue a sensitive agent job and an older customer job; customer wins.
        asyncio_run(database.enqueue_job(
            tenant_id="test",
            ticket_id=101,
            message_id="agent-sensitive",
            event_type="ticket.message.created",
            author_type="agent",
            is_customer_message=False,
            payload={
                "message_id": "agent-sensitive",
                "ticket_subject": "Chargeback",
                "message_text": "I will dispute this charge",
                "ticket_id": 101,
                "intents": [],
            },
            db_path=self.path,
        ))
        asyncio_run(Database(self.path).execute(
            "UPDATE job_queue SET created_at = ? WHERE message_id = ?",
            ("2026-01-01T00:00:00+00:00", "agent-sensitive"),
            operation="test_set_agent_created_at",
        ))
        self._enqueue("customer-normal", subject="Order status", text="Where is my order?", created_at="2026-01-01T00:01:00+00:00")

        selected = orchestrator._select_next_job(self._window())

        self.assertEqual(selected["message_id"], "customer-normal")

    def test_single_job_backlog_skips_extra_classification(self):
        self._enqueue("only-job", subject="Order status", text="Where is my order?", created_at="2026-01-01T00:00:00+00:00")
        orchestrator._classification_cache.clear()

        selected = orchestrator._select_next_job(self._window())

        self.assertEqual(selected["message_id"], "only-job")
        self.assertEqual(orchestrator._classification_cache, {})

    def test_classification_is_cached_for_selected_job(self):
        self._enqueue("normal-one", subject="Order status", text="Where is my order?", created_at="2026-01-01T00:00:00+00:00")
        self._enqueue("sensitive-two", subject="Chargeback", text="I will dispute this charge", created_at="2026-01-01T00:01:00+00:00")

        selected = orchestrator._select_next_job(self._window())
        self.assertEqual(selected["message_id"], "sensitive-two")
        self.assertIn("sensitive-two", orchestrator._classification_cache)
        self.assertIn("normal-one", orchestrator._classification_cache)

        # Selection is idempotent and reuses the cache.
        selected_again = orchestrator._select_next_job(self._window())
        self.assertEqual(selected_again["message_id"], "sensitive-two")

        orchestrator._classification_cache.clear()

    def test_unclassifiable_job_does_not_block_sensitive_selection(self):
        self._enqueue(
            "corrupt",
            subject="Order status",
            text="Where is my order?",
            created_at="2026-01-01T00:00:00+00:00",
        )
        asyncio_run(Database(self.path).execute(
            "UPDATE job_queue SET payload = ? WHERE message_id = ?",
            ("{not-json", "corrupt"),
            operation="test_corrupt_payload",
        ))
        self._enqueue(
            "sensitive-new",
            subject="Chargeback",
            text="I will dispute this charge",
            created_at="2026-01-01T00:01:00+00:00",
        )

        selected = orchestrator._select_next_job(self._window())

        self.assertEqual(selected["message_id"], "sensitive-new")
        self.assertNotIn("corrupt", orchestrator._classification_cache)

    def test_classify_error_does_not_block_sensitive_selection(self):
        asyncio_run(database.enqueue_job(
            tenant_id="test",
            ticket_id=100,
            message_id="bad-intent",
            event_type="ticket.message.created",
            author_type="customer",
            is_customer_message=True,
            payload={
                "message_id": "bad-intent",
                "ticket_subject": "Hello",
                "message_text": "Hi there",
                "ticket_id": 100,
                "intents": [{"name": 1}],
            },
            db_path=self.path,
        ))
        asyncio_run(Database(self.path).execute(
            "UPDATE job_queue SET created_at = ? WHERE message_id = ?",
            ("2026-01-01T00:00:00+00:00", "bad-intent"),
            operation="test_set_bad_intent_created_at",
        ))
        self._enqueue(
            "sensitive-new",
            subject="Chargeback",
            text="I will dispute this charge",
            created_at="2026-01-01T00:01:00+00:00",
        )

        selected = orchestrator._select_next_job(self._window())

        self.assertEqual(selected["message_id"], "sensitive-new")
        self.assertNotIn("bad-intent", orchestrator._classification_cache)

if __name__ == "__main__":
    unittest.main()
