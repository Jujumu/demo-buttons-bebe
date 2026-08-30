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
from helpdesk.dispatch import TOOLS, dispatch, invoke, list_tools
from helpdesk.http import handle_http
from helpdesk.mcp_server import handle_rpc, tool_descriptors
from helpdesk.fixtures_intake import ADA_TRACKING, CHAT_WITH_1001
from helpdesk.names import SAMPLE_SHOP, TOOL_NAMES
from helpdesk.fixtures_sample import ADA, ORDER_ADA
from helpdesk.tickets import reset as reset_tickets


class ContractTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_tickets()

    def test_thirteen_tools_only(self) -> None:
        self.assertEqual(tuple(list_tools()), TOOL_NAMES)
        self.assertEqual(len(TOOLS), 13)
        self.assertEqual([item["name"] for item in tool_descriptors()], list(TOOL_NAMES))
        self.assertIn("helpdesk.draft_reply", TOOL_NAMES)
        self.assertIn("helpdesk.summarize_thread", TOOL_NAMES)
        self.assertIn("helpdesk.search_macros", TOOL_NAMES)
        self.assertIn("helpdesk.apply_macro", TOOL_NAMES)
        self.assertIn("helpdesk.ingest_email", TOOL_NAMES)
        self.assertIn("helpdesk.ingest_chat", TOOL_NAMES)
        self.assertIn("helpdesk.pull_mailbox", TOOL_NAMES)

    def test_mcp_lists_thirteen_tools(self) -> None:
        reply = handle_rpc({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        names = [tool["name"] for tool in reply["result"]["tools"]]
        self.assertEqual(names, list(TOOL_NAMES))
        self.assertEqual(len(names), 13)

    def _cli(self, argv: list[str]) -> dict:
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = cli_main(argv)
        payload = json.loads(buf.getvalue())
        payload["_exit"] = code
        return payload

    def test_each_tool_same_handler_mcp_vs_cli(self) -> None:
        cases = [
            ("helpdesk.list_tickets", ["list-tickets", "--view", "open", "--limit", "5"], {"view": "open", "limit": 5}),
            ("helpdesk.get_ticket", ["get-ticket", "--ticket-id", "1001"], {"ticketId": "1001"}),
            (
                "helpdesk.get_customer",
                ["get-customer", "--shop", SAMPLE_SHOP, "--customer-id", ADA],
                {"shop": SAMPLE_SHOP, "customerId": ADA},
            ),
            (
                "helpdesk.get_order",
                ["get-order", "--shop", SAMPLE_SHOP, "--order-id", ORDER_ADA],
                {"shop": SAMPLE_SHOP, "orderId": ORDER_ADA},
            ),
            (
                "helpdesk.get_returns",
                ["get-returns", "--shop", SAMPLE_SHOP, "--order-id", ORDER_ADA],
                {"shop": SAMPLE_SHOP, "orderId": ORDER_ADA},
            ),
            (
                "helpdesk.list_past_orders",
                ["list-past-orders", "--shop", SAMPLE_SHOP, "--customer-id", ADA],
                {"shop": SAMPLE_SHOP, "customerId": ADA},
            ),
            (
                "helpdesk.draft_reply",
                ["draft-reply", "--ticket", "1001"],
                {"ticketId": "1001", "shop": SAMPLE_SHOP},
            ),
            (
                "helpdesk.summarize_thread",
                ["summarize-thread", "--ticket", "1001"],
                {"ticketId": "1001", "shop": SAMPLE_SHOP},
            ),
            (
                "helpdesk.search_macros",
                ["search-macros", "--query", "shipping"],
                {"query": "shipping"},
            ),
            (
                "helpdesk.apply_macro",
                ["apply-macro", "--macro-id", "shipping-delay", "--mode", "replace"],
                {"macroId": "shipping-delay", "mode": "replace"},
            ),
            (
                "helpdesk.ingest_email",
                [
                    "ingest-email",
                    "--from",
                    ADA_TRACKING["from"],
                    "--subject",
                    ADA_TRACKING["subject"],
                    "--body",
                    ADA_TRACKING["body"],
                    "--received-at",
                    ADA_TRACKING["receivedAt"],
                ],
                dict(ADA_TRACKING),
            ),
            (
                "helpdesk.ingest_chat",
                [
                    "ingest-chat",
                    "--from-name",
                    CHAT_WITH_1001["fromName"],
                    "--body",
                    CHAT_WITH_1001["body"],
                    "--received-at",
                    CHAT_WITH_1001["receivedAt"],
                ],
                dict(CHAT_WITH_1001),
            ),
            (
                "helpdesk.pull_mailbox",
                ["pull-mailbox", "--limit", "5"],
                {"limit": 5},
            ),
        ]
        for tool, argv, args in cases:
            reset_tickets()
            handled = dispatch(tool, args)
            reset_tickets()
            cli = self._cli(argv)
            reset_tickets()
            mcp = handle_rpc(
                {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "tools/call",
                    "params": {"name": tool, "arguments": args},
                }
            )
            mcp_body = json.loads(mcp["result"]["content"][0]["text"])
            reset_tickets()
            cli.pop("_exit")
            self.assertEqual(handled, cli, tool)
            self.assertEqual(handled, mcp_body, tool)
            self.assertEqual(handled, handle_http(tool, args), tool)
            self.assertTrue(handled["ok"], tool)

    def test_unknown_tool_is_structured_json(self) -> None:
        payload = invoke("helpdesk.send", {})
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"], "forbidden")
        self.assertNotIn("Traceback", json.dumps(payload))


if __name__ == "__main__":
    unittest.main()
