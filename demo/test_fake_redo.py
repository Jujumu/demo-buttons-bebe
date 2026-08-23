from __future__ import annotations

import importlib.util
import json
import os
import unittest
from pathlib import Path


DEMO_DIR = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("fake_redo_mcp", DEMO_DIR / "fake_redo_mcp.py")
assert SPEC and SPEC.loader
fake_redo = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fake_redo)


class FakeRedoTests(unittest.TestCase):
    def test_fixture_is_deterministic_and_covers_demo_orders(self) -> None:
        data = fake_redo.load_fixtures()
        self.assertEqual([order["name"] for order in data["orders"]], ["1001", "1002", "1003", "1004"])
        self.assertEqual(len(data["returns"]), 2)
        self.assertTrue(all(order["test"] for order in data["orders"]))

    def test_fixture_override_is_supported_without_server(self) -> None:
        original = os.environ.get("DEMO_REDO_FIXTURES")
        try:
            os.environ["DEMO_REDO_FIXTURES"] = str(DEMO_DIR / "fixtures" / "redo.json")
            self.assertEqual(fake_redo.fixture_path(), DEMO_DIR / "fixtures" / "redo.json")
        finally:
            if original is None:
                os.environ.pop("DEMO_REDO_FIXTURES", None)
            else:
                os.environ["DEMO_REDO_FIXTURES"] = original

    def test_order_lookup_accepts_hash_and_preserves_tracking(self) -> None:
        unfulfilled = fake_redo.get_order("#1001")
        fulfilled = fake_redo.get_order("1002")
        self.assertEqual(unfulfilled["fulfillment_status"], "unfulfilled")
        self.assertEqual(fulfilled["tracking"]["number"], "AI-DEMO-1002")
        self.assertTrue(fulfilled["test"])

    def test_return_lookup_exposes_refund_and_excludes_unknown_customer_fields(self) -> None:
        result = fake_redo.get_returns_for_order("#1001")
        self.assertEqual(result["count"], 1)
        return_data = result["returns"][0]
        self.assertEqual(return_data["refunds"][0]["status"], "pending")
        self.assertEqual(fake_redo.get_return("demo-return-1004")["status"], "completed")
        self.assertNotIn("email", return_data)
        self.assertNotIn("source", return_data)

    def test_list_is_limited_and_missing_records_fail_closed(self) -> None:
        self.assertEqual(fake_redo.list_recent_returns(1)["count"], 1)
        self.assertEqual(fake_redo.get_order("#9999")["error"], "order not found")
        self.assertEqual(fake_redo.get_return("missing")["error"], "return not found")


if __name__ == "__main__":
    unittest.main()
