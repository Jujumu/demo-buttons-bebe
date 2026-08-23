"""Local WhatsApp simulator for the Cute Things demo.

This is deliberately not a WhatsApp client. It binds to localhost, loads
synthetic inbound messages, and captures outbound owner alerts in a local
outbox so the support pipeline can be tested without Baileys, QR pairing, a
phone number, or an external send.

The outbound route accepts the same Bearer-authenticated JSON shape consumed
by ``processor/whatsapp_notifier.py``. Every accepted message is marked
``simulated`` and is available from ``GET /wa/outbox``.
"""

from __future__ import annotations

import copy
import hmac
import json
import os
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

try:
    from .local_only import require_loopback
except ImportError:  # direct script execution
    from local_only import require_loopback


HERE = Path(__file__).resolve().parent
DEFAULT_FIXTURES = HERE / "fixtures" / "whatsapp.json"
DEFAULT_SECRET = "demo-only-whatsapp-send-secret"
DEFAULT_BASE_PATH = "/connect-whatsapp/demo"


def load_fixture(path: str | os.PathLike[str] | None = None) -> dict[str, Any]:
    fixture_path = Path(path or os.environ.get("DEMO_WHATSAPP_FIXTURES", DEFAULT_FIXTURES))
    data = json.loads(fixture_path.read_text(encoding="utf-8"))
    identity = data.get("identity")
    inbound = data.get("inbound")
    if not isinstance(identity, dict) or identity.get("state") != "connected":
        raise ValueError("WhatsApp fixture must describe a connected demo identity")
    if not isinstance(inbound, list) or not inbound:
        raise ValueError("WhatsApp fixture must contain inbound messages")
    if not all(bool(message.get("synthetic")) for message in inbound):
        raise ValueError("every WhatsApp fixture message must be synthetic")
    return data


def _read_json(handler: BaseHTTPRequestHandler) -> dict[str, Any]:
    try:
        length = int(handler.headers.get("Content-Length", "0"))
    except ValueError:
        raise ValueError("invalid content length") from None
    if length <= 0 or length > 20_000:
        raise ValueError("request body must be between 1 and 20000 bytes")
    raw = handler.rfile.read(length)
    value = json.loads(raw.decode("utf-8"))
    if not isinstance(value, dict):
        raise ValueError("request body must be a JSON object")
    return value


class DemoWhatsAppState:
    """Thread-safe in-memory simulator state with an optional local outbox."""

    def __init__(
        self,
        fixture_path: str | os.PathLike[str] | None = None,
        outbox_path: str | os.PathLike[str] | None = None,
        send_secret: str | None = None,
        base_path: str = DEFAULT_BASE_PATH,
    ) -> None:
        fixture = load_fixture(fixture_path)
        self.identity = copy.deepcopy(fixture["identity"])
        self.inbox = copy.deepcopy(fixture["inbound"])
        self.outbox: list[dict[str, Any]] = []
        self.send_secret = send_secret or os.environ.get("DEMO_WA_SEND_SECRET", DEFAULT_SECRET)
        self.base_path = "/" + base_path.strip("/")
        self.outbox_path = Path(outbox_path) if outbox_path else None
        self._lock = threading.Lock()

    def status(self) -> dict[str, Any]:
        return {
            "state": self.identity["state"],
            "qr": None,
            "owner": self.identity["owner_jid"],
            "display_name": self.identity.get("display_name", "Demo owner"),
            "simulated": True,
            "delivery": "local_capture_only",
        }

    def capture_outbound(self, text: str) -> dict[str, Any]:
        with self._lock:
            message = {
                "id": f"demo-wa-out-{len(self.outbox) + 1:03d}",
                "to": self.identity["owner_jid"],
                "text": text[:4000],
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "simulated": True,
                "delivered": False,
                "delivery": "captured_locally",
            }
            self.outbox.append(message)
            if self.outbox_path:
                self.outbox_path.parent.mkdir(parents=True, exist_ok=True)
                with self.outbox_path.open("a", encoding="utf-8") as stream:
                    stream.write(json.dumps(message, ensure_ascii=False) + "\n")
            return copy.deepcopy(message)

    def add_inbound(self, text: str, sender: str | None = None) -> dict[str, Any]:
        if not text.strip():
            raise ValueError("text is required")
        with self._lock:
            message = {
                "id": f"demo-wa-in-live-{len(self.inbox) + 1:03d}",
                "from": sender or self.identity["owner_jid"],
                "text": text[:4000],
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "synthetic": True,
                "simulated": True,
            }
            self.inbox.append(message)
            return copy.deepcopy(message)


def _authorized(header: str | None, expected: str) -> bool:
    if not isinstance(header, str):
        return False
    scheme, separator, credential = header.partition(" ")
    return bool(separator and scheme.lower() == "bearer" and
                hmac.compare_digest(credential.strip(), expected))


def create_server(
    host: str = "127.0.0.1",
    port: int = 8185,
    state: DemoWhatsAppState | None = None,
) -> ThreadingHTTPServer:
    require_loopback(host, "fake WhatsApp")
    demo_state = state or DemoWhatsAppState(
        outbox_path=os.environ.get("DEMO_WA_OUTBOX"),
        base_path=os.environ.get("DEMO_WA_BASE_PATH", DEFAULT_BASE_PATH),
    )

    class Handler(BaseHTTPRequestHandler):
        server_version = "CuteThingsDemoWhatsApp/1.0"

        @property
        def demo_state(self) -> DemoWhatsAppState:
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
            if path in {"/health", "/wa/status"}:
                return self._send(HTTPStatus.OK, self.demo_state.status())
            if path == "/wa/inbox":
                return self._send(HTTPStatus.OK, {"count": len(self.demo_state.inbox), "messages": self.demo_state.inbox})
            if path == "/wa/outbox":
                return self._send(HTTPStatus.OK, {"count": len(self.demo_state.outbox), "messages": self.demo_state.outbox})
            return self._send(HTTPStatus.NOT_FOUND, {"error": "not found"})

        def do_POST(self) -> None:  # noqa: N802
            path = urlsplit(self.path).path
            send_path = {"/send", self.demo_state.base_path + "/send"}
            if path in send_path:
                if not _authorized(self.headers.get("Authorization"), self.demo_state.send_secret):
                    return self._send(HTTPStatus.UNAUTHORIZED, {"error": "unauthorized"})
                try:
                    body = _read_json(self)
                    text = str(body.get("text", "")).strip()
                    if not text:
                        raise ValueError("text is required")
                    message = self.demo_state.capture_outbound(text)
                except (ValueError, json.JSONDecodeError) as exc:
                    return self._send(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
                return self._send(HTTPStatus.OK, {"ok": True, **message})

            if path == "/simulate/inbound":
                try:
                    body = _read_json(self)
                    message = self.demo_state.add_inbound(str(body.get("text", "")), body.get("from"))
                except (ValueError, json.JSONDecodeError) as exc:
                    return self._send(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
                return self._send(HTTPStatus.CREATED, message)

            if path == "/wa/test":
                message = self.demo_state.capture_outbound(
                    "✅ Simulated WhatsApp alert. No phone message was sent."
                )
                return self._send(HTTPStatus.OK, {"ok": True, **message})

            return self._send(HTTPStatus.NOT_FOUND, {"error": "not found"})

        def log_message(self, _format: str, *_args: Any) -> None:
            return

    server = ThreadingHTTPServer((host, port), Handler)
    server.demo_state = demo_state  # type: ignore[attr-defined]
    return server


def main() -> None:
    port = int(os.environ.get("DEMO_WHATSAPP_PORT", "8185"))
    server = create_server(host="127.0.0.1", port=port)
    print(f"fake WhatsApp listening on http://127.0.0.1:{port} (local capture only)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
