"""Local, read-only knowledge-base MCP service for the Cute Things demo.

The production KB uses LanceDB and embeddings. This emulator deliberately has
no network, model download, credentials, or mutable state: it loads a small
JSON fixture and ranks matching passages with deterministic token overlap.

Run with ``KB_MCP_TRANSPORT=streamable-http`` for Hermes, or use the pure
``search_fixture`` helper in tests and local smoke checks.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

try:
    from .local_only import require_loopback
except ImportError:  # direct script execution
    from local_only import require_loopback


HERE = Path(__file__).resolve().parent
DEFAULT_FIXTURES = HERE / "fixtures" / "kb.json"
HOST = require_loopback(
    os.environ.get("KB_MCP_HOST", "127.0.0.1"),
    "fake KB MCP",
)
PORT = int(os.environ.get("KB_MCP_PORT", "8177"))
TRANSPORT = os.environ.get("KB_MCP_TRANSPORT", "stdio")

_STOP_WORDS = {
    "a", "an", "and", "are", "be", "can", "do", "for", "has", "how",
    "i", "in", "is", "it", "my", "of", "on", "or", "the", "to", "was",
    "what", "when", "where", "why", "with", "you", "your",
}


def _tokens(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+", value.lower())
        if token not in _STOP_WORDS and len(token) > 1
    }


def load_fixture(path: str | os.PathLike[str] | None = None) -> list[dict[str, Any]]:
    """Load and validate the immutable demo documents."""
    fixture_path = Path(path or os.environ.get("DEMO_KB_FIXTURES", DEFAULT_FIXTURES))
    raw = json.loads(fixture_path.read_text(encoding="utf-8"))
    documents = raw.get("documents")
    if not isinstance(documents, list) or not documents:
        raise ValueError("KB fixture must contain a non-empty documents list")

    required = {"id", "file", "title", "category", "status", "sensitive", "heading", "text"}
    normalized: list[dict[str, Any]] = []
    for document in documents:
        if not required.issubset(document):
            missing = ", ".join(sorted(required - set(document)))
            raise ValueError(f"KB document is missing: {missing}")
        copy = dict(document)
        copy["sensitive"] = bool(copy["sensitive"])
        copy["tags"] = list(copy.get("tags", []))
        normalized.append(copy)
    return normalized


def _search_score(query: str, document: dict[str, Any]) -> float:
    query_tokens = _tokens(query)
    if not query_tokens:
        return 0.0
    title_tokens = _tokens(str(document["title"]))
    heading_tokens = _tokens(str(document["heading"]))
    body_tokens = _tokens(str(document["text"]))
    tag_tokens = _tokens(" ".join(document.get("tags", [])))
    score = (
        4.0 * len(query_tokens & title_tokens)
        + 3.0 * len(query_tokens & heading_tokens)
        + 2.0 * len(query_tokens & tag_tokens)
        + 1.0 * len(query_tokens & body_tokens)
    )
    if query.strip().lower() in str(document["text"]).lower():
        score += 2.0
    return score / max(len(query_tokens), 1)


def search_fixture(query: str, k: int = 5, documents: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """Return the same stable result fields as the production ``search_kb`` tool."""
    if k <= 0:
        return []
    docs = documents if documents is not None else load_fixture()
    ranked = [(_search_score(query, document), index, document) for index, document in enumerate(docs)]
    ranked = [item for item in ranked if item[0] > 0]
    ranked.sort(key=lambda item: (-item[0], item[1]))
    return [
        {
            "score": round(score, 4),
            "file": document["file"],
            "title": document["title"],
            "category": document["category"],
            "status": document["status"],
            "sensitive": document["sensitive"],
            "heading": document["heading"],
            "text": f"{document['title']} -- {document['heading']}\n\n{document['text']}",
        }
        for score, _index, document in ranked[:k]
    ]


def build_mcp():
    """Create the MCP server lazily so fixture tests need no MCP dependency."""
    from mcp.server.fastmcp import FastMCP

    mcp = FastMCP("cute-things-demo-kb", host=HOST, port=PORT)

    @mcp.tool()
    def search_kb(query: str, k: int = 5) -> list[dict[str, Any]]:
        """Search the isolated Cute Things demo knowledge base (read-only)."""
        return search_fixture(query, k=k)

    return mcp


if __name__ == "__main__":
    build_mcp().run(transport=TRANSPORT)
