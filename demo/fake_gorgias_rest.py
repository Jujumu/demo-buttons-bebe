"""Local-only REST sink for human Gorgias console actions.

It mirrors the two dashboard action routes used by the real console.  A
successful send or note is captured in memory (and optionally as local JSONL),
but it never forwards anything to Gorgias, Shopify, WhatsApp, or the network.
"""

from __future__ import annotations

import copy
import json
import os
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from fake_gorgias_mcp import load_fixtures


DEFAULT_PORT = 8190
ACTION_PATHS = {
    "/dashboard/api/ticket/{ticket_id}/send": "send",
    "/dashboard/api/ticket/{ticket_id}/note": "note",
    "/console/api/ticket/{ticket_id}/send": "send",
    "/console/api/ticket/{ticket_id}/note": "note",
}


def _read_json(handler: BaseHTTPRequestHandler) -> dict[str, Any]:
    try:
        length = int(handler.headers.get("Content-Length", "0"))
    except ValueError:
        raise ValueError("invalid content length") from None
    if length <= 0 or length > 50_000:
        raise ValueError("request body must be between 1 and 50000 bytes")
    value = json.loads(handler.rfile.read(length).decode("utf-8"))
    if not isinstance(value, dict):
        raise ValueError("request body must be a JSON object")
    return value


def _action_route(path: str) -> tuple[str, int] | None:
    parts = urlsplit(path).path.strip("/").split("/")
    if len(parts) != 5 or parts[0] not in {"dashboard", "console"} or parts[1] != "api":
        return None
    if parts[2] != "ticket" or parts[4] not in {"send", "note"}:
        return None
    try:
        ticket_id = int(parts[3])
    except ValueError:
        return None
    return parts[4], ticket_id


class DemoGorgiasState:
    """Thread-safe local action capture with synthetic-ticket validation."""

    def __init__(self, fixture_path: str | os.PathLike[str] | None = None, action_log: str | os.PathLike[str] | None = None) -> None:
        fixture = load_fixtures(fixture_path)
        self.tickets = {int(item["id"]): copy.deepcopy(item) for item in fixture["tickets"]}
        self.customers = {int(item["id"]): copy.deepcopy(item) for item in fixture["customers"]}
        self.actions: list[dict[str, Any]] = []
        self.action_log = Path(action_log) if action_log else None
        self._lock = threading.Lock()

    def capture(self, kind: str, ticket_id: int, body: dict[str, Any]) -> dict[str, Any]:
        text = str(
            body.get("text") or body.get("body_text") or body.get("body_html") or ""
        ).strip()
        if not text:
            raise ValueError("empty reply" if kind == "send" else "empty note")
        if ticket_id not in self.tickets:
            raise LookupError("ticket not found")
        with self._lock:
            action = {
                "id": f"demo-gorgias-action-{len(self.actions) + 1:03d}",
                "kind": kind,
                "ticket_id": ticket_id,
                "text": text,
                "public": kind == "send",
                "simulated": True,
                "delivered": False,
                "delivery": "captured_locally",
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "metadata": {
                    key: copy.deepcopy(body[key])
                    for key in ("message_text", "ai_draft", "customer_name")
                    if key in body
                },
            }
            self.actions.append(action)
            if self.action_log:
                self.action_log.parent.mkdir(parents=True, exist_ok=True)
                with self.action_log.open("a", encoding="utf-8") as stream:
                    stream.write(json.dumps(action, ensure_ascii=False) + "\n")
            return copy.deepcopy(action)


def create_server(
    host: str = "127.0.0.1",
    port: int = DEFAULT_PORT,
    state: DemoGorgiasState | None = None,
) -> ThreadingHTTPServer:
    """Create a localhost-bound action sink for tests or the demo process."""

    if host not in {"127.0.0.1", "localhost"}:
        raise ValueError("fake Gorgias REST sink only permits localhost")
    demo_state = state or DemoGorgiasState(
        action_log=os.environ.get("DEMO_GORGIAS_ACTION_LOG")
    )

    class Handler(BaseHTTPRequestHandler):
        server_version = "CuteThingsDemoGorgiasREST/1.0"

        @property
        def demo_state(self) -> DemoGorgiasState:
            return self.server.demo_state  # type: ignore[attr-defined]

        def _send(self, status: int, payload: dict[str, Any]) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:  # noqa: N802
            path = urlsplit(self.path).path
            if path in {"/health", "/dashboard/api/actions", "/console/api/actions"}:
                return self._send(
                    HTTPStatus.OK,
                    {
                        "ok": True,
                        "simulated": True,
                        "delivery": "local_capture_only",
                        "count": len(self.demo_state.actions),
                        "actions": copy.deepcopy(self.demo_state.actions),
                    },
                )
            parts = path.strip("/").split("/")
            if len(parts) == 4 and parts[:2] == ["api", "tickets"] and parts[3] == "messages":
                try:
                    ticket_id = int(parts[2])
                except ValueError:
                    return self._send(HTTPStatus.BAD_REQUEST, {"error": "invalid ticket id"})
                ticket = self.demo_state.tickets.get(ticket_id)
                if ticket is None:
                    return self._send(HTTPStatus.NOT_FOUND, {"error": "ticket not found"})
                return self._send(
                    HTTPStatus.OK,
                    {"data": copy.deepcopy(ticket.get("messages", []))},
                )
            if len(parts) == 3 and parts[:2] == ["api", "tickets"]:
                try:
                    ticket_id = int(parts[2])
                except ValueError:
                    return self._send(HTTPStatus.BAD_REQUEST, {"error": "invalid ticket id"})
                ticket = self.demo_state.tickets.get(ticket_id)
                if ticket is None:
                    return self._send(HTTPStatus.NOT_FOUND, {"error": "ticket not found"})
                payload = copy.deepcopy(ticket)
                payload.pop("synthetic", None)
                return self._send(HTTPStatus.OK, payload)
            if path == "/api/tickets":
                tickets = [copy.deepcopy(ticket) for ticket in self.demo_state.tickets.values()]
                return self._send(HTTPStatus.OK, {"data": tickets})
            return self._send(HTTPStatus.NOT_FOUND, {"error": "not found"})

        def do_POST(self) -> None:  # noqa: N802
            route = _action_route(self.path)
            path = urlsplit(self.path).path
            parts = path.strip("/").split("/")
            api_route = (
                len(parts) == 4
                and parts[:2] == ["api", "tickets"]
                and parts[3] == "messages"
            )
            if api_route:
                try:
                    ticket_id = int(parts[2])
                    body = _read_json(self)
                    kind = (
                        "note"
                        if body.get("public") is False or body.get("channel") == "internal-note"
                        else "send"
                    )
                    action = self.demo_state.capture(kind, ticket_id, body)
                except LookupError as exc:
                    return self._send(HTTPStatus.NOT_FOUND, {"error": str(exc)})
                except (ValueError, json.JSONDecodeError) as exc:
                    return self._send(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
                return self._send(HTTPStatus.CREATED, action)
            if route is None:
                return self._send(HTTPStatus.NOT_FOUND, {"error": "not found"})
            kind, ticket_id = route
            try:
                body = _read_json(self)
                action = self.demo_state.capture(kind, ticket_id, body)
            except LookupError as exc:
                return self._send(HTTPStatus.NOT_FOUND, {"error": str(exc)})
            except (ValueError, json.JSONDecodeError) as exc:
                return self._send(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            return self._send(HTTPStatus.OK, {"ok": True, **action})

        def log_message(self, _format: str, *_args: Any) -> None:
            return

    server = ThreadingHTTPServer((host, port), Handler)
    server.demo_state = demo_state  # type: ignore[attr-defined]
    return server


def main() -> None:
    port = int(os.environ.get("DEMO_GORGIAS_PORT", str(DEFAULT_PORT)))
    server = create_server(host="127.0.0.1", port=port)
    print(f"fake Gorgias REST sink listening on http://127.0.0.1:{port} (local capture only)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
