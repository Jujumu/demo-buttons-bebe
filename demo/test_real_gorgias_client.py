"""Real GorgiasClient against the localhost-only Cute Things simulator."""

from __future__ import annotations

import os
import sys
import threading
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "demo"
WEBHOOK_SRC = ROOT / "webhook" / "src"
sys.path[:0] = [str(DEMO), str(WEBHOOK_SRC)]

import dotenv  # noqa: E402

os.environ.update({
    "WEBHOOK_SECRET": "demo-only-gorgias-client-test",
    "GORGIAS_SUBDOMAIN": "cute-things-demo",
    "GORGIAS_API_EMAIL": "demo-agent@example.com",
    "GORGIAS_API_KEY": "demo-only-local-key",
})

with patch.object(dotenv, "load_dotenv", lambda *_args, **_kwargs: False):
    from bb_webhook.config import Settings, get_settings  # noqa: E402
    from bb_webhook.gorgias_client import GorgiasClient  # noqa: E402
    from fake_gorgias_rest import DemoGorgiasState, create_server  # noqa: E402

Settings.model_config["env_file"] = None


class RealGorgiasClientDemoTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.state = DemoGorgiasState()
        self.server = create_server(host="127.0.0.1", port=0, state=self.state)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = f"http://127.0.0.1:{self.server.server_address[1]}"
        get_settings.cache_clear()
        # Pass every external boundary explicitly so this integration test is
        # independent of environment mutations made by other test modules.
        self.client = GorgiasClient(
            subdomain="cute-things-demo",
            email="demo-agent@example.com",
            api_key="demo-only-local-key",
            base_url=self.base_url,
        )

    async def asyncTearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        get_settings.cache_clear()

    async def test_reads_the_synthetic_ticket(self) -> None:
        ticket = await self.client.get_ticket(61002)
        self.assertIsNotNone(ticket)
        self.assertEqual(ticket["customer"]["email"], "ai-demo-fulfilled@example.com")

    async def test_public_reply_uses_message_channel_and_is_only_captured(self) -> None:
        result = await self.client.send_public_reply(61002, "Demo public reply")
        self.assertTrue(result["ok"])
        self.assertEqual(self.state.actions[-1]["kind"], "send")
        self.assertFalse(self.state.actions[-1]["delivered"])

    async def test_internal_note_is_only_captured(self) -> None:
        result = await self.client.post_internal_note(61004, "Demo internal note")
        self.assertTrue(result["ok"])
        self.assertEqual(self.state.actions[-1]["kind"], "note")
        self.assertFalse(self.state.actions[-1]["delivered"])

    async def test_missing_ticket_fails_closed_without_capture(self) -> None:
        result = await self.client.send_public_reply(999999, "Must not be captured")
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "ticket not found")
        self.assertEqual(self.state.actions, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
