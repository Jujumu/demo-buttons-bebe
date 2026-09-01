"""Local review door: inbox static files + the same helpdesk invoke() path."""

from __future__ import annotations

import argparse
import json
import os
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sys

INBOX = Path(__file__).resolve().parent
AGENT = INBOX.parent / "helpdesk-agent"
REPO = INBOX.parents[1]
sys.path.insert(0, str(AGENT))


def _load_dotenv(path: Path) -> None:
    """Load KEY=VALUE from .env into os.environ when unset. Never prints values."""
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text or text.startswith("#") or "=" not in text:
            continue
        key, raw = text.split("=", 1)
        key = key.strip()
        if not key or key in os.environ:
            continue
        os.environ[key] = raw.strip().strip("\"'")


_load_dotenv(REPO / ".env")
os.environ.setdefault("SHOPIFY_MUTATIONS_ENABLED", "0")

from helpdesk.http import handle_http  # noqa: E402


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(INBOX), **kwargs)

    def end_headers(self):
        # Inbox is ES modules; avoid stale JS after deploys.
        if self.path.split("?", 1)[0].endswith((".js", ".css", ".html")):
            self.send_header("Cache-Control", "no-store")
        super().end_headers()

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
    parser = argparse.ArgumentParser(description="Inbox review server")
    parser.add_argument("--host", default=os.environ.get("INBOX_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("INBOX_PORT", "8765")))
    args = parser.parse_args()
    main(host=args.host, port=args.port)
