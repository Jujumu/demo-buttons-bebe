#!/usr/bin/env python3
"""Local-only console host that proxies `/console/api` to the demo webhook."""

from __future__ import annotations

import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
CONSOLE = ROOT / "console-src" / "index.html"
UPSTREAM = "http://127.0.0.1:8100"


class Handler(BaseHTTPRequestHandler):
    server_version = "CuteThingsDemoConsole/1.0"

    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _proxy(self) -> None:
        parsed = urlsplit(self.path)
        if not parsed.path.startswith("/console/api/"):
            return self._send(HTTPStatus.NOT_FOUND, b"not found", "text/plain")
        upstream_path = "/dashboard/api/" + parsed.path.removeprefix("/console/api/")
        if parsed.query:
            upstream_path += "?" + parsed.query
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length < 0 or length > 100_000:
            return self._send(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, b"too large", "text/plain")
        body = self.rfile.read(length) if length else None
        request = Request(
            UPSTREAM + upstream_path,
            data=body,
            method=self.command,
            headers={"Content-Type": self.headers.get("Content-Type", "application/json")},
        )
        try:
            with urlopen(request, timeout=180) as response:
                payload = response.read()
                content_type = response.headers.get("Content-Type", "application/json")
                return self._send(response.status, payload, content_type)
        except HTTPError as exc:
            return self._send(
                exc.code,
                exc.read(),
                exc.headers.get("Content-Type", "application/json"),
            )
        except URLError:
            return self._send(
                HTTPStatus.BAD_GATEWAY,
                b'{"error":"demo webhook unavailable"}',
                "application/json",
            )

    def do_GET(self) -> None:  # noqa: N802
        if urlsplit(self.path).path in {"/", "/console", "/console/"}:
            page = CONSOLE.read_text(encoding="utf-8").replace(
                "Buttons Bebe", "Cute Things"
            )
            return self._send(
                HTTPStatus.OK,
                page.encode("utf-8"),
                "text/html; charset=utf-8",
            )
        return self._proxy()

    def do_POST(self) -> None:  # noqa: N802
        return self._proxy()

    def log_message(self, _format: str, *_args: object) -> None:
        return


def main() -> None:
    port = int(os.environ.get("DEMO_CONSOLE_PORT", "8101"))
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"demo console listening on http://127.0.0.1:{port}/")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
