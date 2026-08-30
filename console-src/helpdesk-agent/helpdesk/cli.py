"""CLI door. Same handlers as MCP. JSON stdout."""

from __future__ import annotations

import argparse
import json
import sys

from .dispatch import invoke, list_tools
from .names import (
    CLI_COMMANDS,
    SAMPLE_SHOP,
    TOOL_DRAFT_REPLY,
    TOOL_GET_CUSTOMER,
    TOOL_GET_ORDER,
    TOOL_GET_RETURNS,
    TOOL_GET_TICKET,
    TOOL_LIST_PAST_ORDERS,
    TOOL_LIST_TICKETS,
    TOOL_SUMMARIZE_THREAD,
)


def _print(payload: dict) -> int:
    json.dump(payload, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0 if payload.get("ok") else 1


def _add_shop_gid(parser: argparse.ArgumentParser, gid_flag: str, dest: str) -> None:
    parser.add_argument("--shop", default=SAMPLE_SHOP)
    parser.add_argument(gid_flag, dest=dest, required=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="helpdesk", description="Shopify helpdesk organ (MCP + CLI).")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("tools", help="list the eight v1 tools")
    sub.add_parser("serve", help="run the MCP stdio server")
    tickets = sub.add_parser(CLI_COMMANDS[TOOL_LIST_TICKETS])
    tickets.add_argument("--view", default="open")
    tickets.add_argument("--limit", type=int, default=20)
    get_ticket = sub.add_parser(CLI_COMMANDS[TOOL_GET_TICKET])
    get_ticket.add_argument("--ticket-id", dest="ticketId", required=True)
    _add_shop_gid(sub.add_parser(CLI_COMMANDS[TOOL_GET_CUSTOMER]), "--customer-id", "customerId")
    _add_shop_gid(sub.add_parser(CLI_COMMANDS[TOOL_GET_ORDER]), "--order-id", "orderId")
    _add_shop_gid(sub.add_parser(CLI_COMMANDS[TOOL_GET_RETURNS]), "--order-id", "orderId")
    _add_shop_gid(sub.add_parser(CLI_COMMANDS[TOOL_LIST_PAST_ORDERS]), "--customer-id", "customerId")
    draft = sub.add_parser(CLI_COMMANDS[TOOL_DRAFT_REPLY])
    draft.add_argument("--ticket", dest="ticketId", required=True)
    draft.add_argument("--shop", default=SAMPLE_SHOP)
    summarize = sub.add_parser(CLI_COMMANDS[TOOL_SUMMARIZE_THREAD])
    summarize.add_argument("--ticket", dest="ticketId", required=True)
    summarize.add_argument("--shop", default=SAMPLE_SHOP)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "tools":
        return _print({"ok": True, "tools": list_tools()})
    if args.command == "serve":
        from .mcp_server import run_stdio

        run_stdio()
        return 0
    inverse = {value: key for key, value in CLI_COMMANDS.items()}
    tool = inverse[args.command]
    payload = {key: value for key, value in vars(args).items() if key != "command" and value is not None}
    return _print(invoke(tool, payload))


if __name__ == "__main__":
    raise SystemExit(main())
