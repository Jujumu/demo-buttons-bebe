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
from helpdesk.names import SAMPLE_SHOP, TOOL_NAMES
from helpdesk.fixtures_sample import ADA, ORDER_ADA


class ContractTests(unittest.TestCase):
    def test_eight_tools_only(self) -> None:
        self.assertEqual(tuple(list_tools()), TOOL_NAMES)
        self.assertEqual(len(TOOLS), 8)
        self.assertEqual([item["name"] for item in tool_descriptors()], list(TOOL_NAMES))
        self.assertIn("helpdesk.draft_reply", TOOL_NAMES)
        self.assertIn("helpdesk.summarize_thread", TOOL_NAMES)

    def test_mcp_lists_eight_tools(self) -> None:
        reply = handle_rpc({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        names = [tool["name"] for tool in reply["result"]["tools"]]
        self.assertEqual(names, list(TOOL_NAMES))
        self.assertEqual(len(names), 8)

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
        ]
        for tool, argv, args in cases:
            handled = dispatch(tool, args)
            cli = self._cli(argv)
            mcp = handle_rpc(
                {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "tools/call",
                    "params": {"name": tool, "arguments": args},
                }
            )
            mcp_body = json.loads(mcp["result"]["content"][0]["text"])
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
