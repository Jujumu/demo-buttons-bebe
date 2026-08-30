from __future__ import annotations

import json
import os
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from helpdesk.dispatch import WRITE_TOOLS, dispatch, invoke
from helpdesk.macros import MACROS
from helpdesk.mcp_server import handle_rpc
from helpdesk.names import TOOL_NAMES


FORBIDDEN = (
    "gorgias",
    "malky",
    "rivky",
    "sperber",
    "morgenstern",
    "refund you",
    "i cancelled",
    "i refunded",
    "shpat_",
)


class MacroTissueTests(unittest.TestCase):
    def test_search_macros_lists_fixture_bodies(self) -> None:
        payload = dispatch("helpdesk.search_macros", {})
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["source"], "fixture")
        ids = [row["id"] for row in payload["macros"]]
        self.assertEqual(ids, ["shipping-delay", "return-how-to", "order-status"])
        self.assertEqual(len(payload["macros"]), 3)
        for row in payload["macros"]:
            self.assertEqual(set(row), {"id", "title", "body", "tags"})
            self.assertTrue(row["title"])
            self.assertGreater(len(row["body"]), 20)
            blob = json.dumps(row).lower()
            for snippet in FORBIDDEN:
                self.assertNotIn(snippet, blob, snippet)

    def test_search_query_filters_title_and_tags(self) -> None:
        delay = dispatch("helpdesk.search_macros", {"query": "delay"})
        self.assertEqual([row["id"] for row in delay["macros"]], ["shipping-delay"])
        returns = dispatch("helpdesk.search_macros", {"query": "return"})
        self.assertEqual([row["id"] for row in returns["macros"]], ["return-how-to"])
        status = dispatch("helpdesk.search_macros", {"query": "status"})
        self.assertEqual([row["id"] for row in status["macros"]], ["order-status"])
        ship = dispatch("helpdesk.search_macros", {"query": "shipping"})
        self.assertEqual({row["id"] for row in ship["macros"]}, {"shipping-delay", "order-status"})
        miss = dispatch("helpdesk.search_macros", {"query": "no-such-macro"})
        self.assertEqual(miss["macros"], [])

    def test_apply_macro_replace_and_append_never_send(self) -> None:
        replaced = dispatch("helpdesk.apply_macro", {"macroId": "shipping-delay", "mode": "replace"})
        self.assertTrue(replaced["ok"])
        self.assertEqual(replaced["mode"], "replace")
        self.assertEqual(replaced["title"], "Shipping delay")
        self.assertEqual(replaced["text"], replaced["body"])
        self.assertIn("carrier update", replaced["text"])

        current = "Hi Ada — checking #1001 now."
        appended = dispatch(
            "helpdesk.apply_macro",
            {"macroId": "order-status", "mode": "append", "currentBody": current},
        )
        self.assertTrue(appended["ok"])
        self.assertEqual(appended["mode"], "append")
        self.assertTrue(appended["text"].startswith(current))
        self.assertIn(appended["body"], appended["text"])
        self.assertIn("I looked at this order", appended["text"])

        for tool in ("helpdesk.search_macros", "helpdesk.apply_macro"):
            self.assertNotIn(tool, WRITE_TOOLS)

    def test_apply_unknown_macro_is_not_found(self) -> None:
        payload = invoke("helpdesk.apply_macro", {"macroId": "missing"})
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"], "not_found")

    def test_apply_bad_mode_is_bad_request(self) -> None:
        payload = invoke("helpdesk.apply_macro", {"macroId": "shipping-delay", "mode": "send"})
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"], "bad_request")

    def test_writes_stay_forbidden(self) -> None:
        os.environ["SHOPIFY_MUTATIONS_ENABLED"] = "0"
        for tool in ("helpdesk.send", "helpdesk.refund", "helpdesk.cancel"):
            payload = invoke(tool, {"macroId": "shipping-delay"})
            self.assertFalse(payload["ok"])
            self.assertEqual(payload["error"], "forbidden")
            self.assertIn("SHOPIFY_MUTATIONS_ENABLED stays 0", payload["message"])

    def test_mcp_lists_macro_tools(self) -> None:
        reply = handle_rpc({"jsonrpc": "2.0", "id": 11, "method": "tools/list"})
        names = [tool["name"] for tool in reply["result"]["tools"]]
        self.assertEqual(names, list(TOOL_NAMES))
        self.assertEqual(len(names), 13)
        self.assertIn("helpdesk.search_macros", names)
        self.assertIn("helpdesk.apply_macro", names)
        self.assertIn("helpdesk.ingest_email", names)
        self.assertIn("helpdesk.ingest_chat", names)
        self.assertIn("helpdesk.pull_mailbox", names)

    def test_payload_has_no_token_or_gorgias_keys(self) -> None:
        payload = dispatch("helpdesk.search_macros", {"query": ""})
        blob = json.dumps({"macros": MACROS, **payload}).lower()
        self.assertNotIn("shpat_", blob)
        self.assertNotIn("gorgias", blob)
        self.assertNotIn("client_secret", blob)


if __name__ == "__main__":
    unittest.main()
