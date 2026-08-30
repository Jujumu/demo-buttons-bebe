"""Local review door: inbox static files + the same helpdesk invoke() path."""

from __future__ import annotations

import json
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sys

INBOX = Path(__file__).resolve().parent
AGENT = INBOX.parent / "helpdesk-agent"
sys.path.insert(0, str(AGENT))

from helpdesk.http import handle_http  # noqa: E402


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(INBOX), **kwargs)

    def do_POST(self):
        if self.path.split("?", 1)[0] != "/console/api/helpdesk":
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            body = json.loads(raw.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            body = {}
        payload = handle_http(body.get("tool"), body.get("arguments") or {})
        encoded = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, format, *args):
        sys.stderr.write("%s - %s\n" % (self.address_string(), format % args))


def main(host: str = "127.0.0.1", port: int = 8765) -> None:
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"inbox review http://{host}:{port}/index.html", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
