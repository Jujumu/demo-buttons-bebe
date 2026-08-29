"""Shared helpers for the Buttons Bebe integration tool modules (Redo, Gorgias).

Each integration is its own module (its own MCP server + systemd service + port +
Hermes tool). They only share this tiny helper for reading the app's .env.
"""
from __future__ import annotations

import os
import pathlib
import re

_TOOLS_DIR = pathlib.Path(__file__).resolve().parent
_REPO_ROOT = _TOOLS_DIR.parent

ENV_CANDIDATES = [
    _REPO_ROOT / ".env",
    _REPO_ROOT / "webhook" / ".env",
]


def _clean(v: str) -> str:
    # remove paste artifacts (surrounding quotes/space, trailing backslashes, CR)
    return re.sub(r'^[\s"\']+|[\s"\'\\]+$', "", v).replace("\r", "")


def load_env() -> dict:
    env: dict = {}
    for fp in ENV_CANDIDATES:
        if not fp.exists():
            continue
        for line in fp.read_text().splitlines():
            s = line.strip()
            if not s or s.startswith("#") or "=" not in s:
                continue
            k, v = s.split("=", 1)
            k, v = k.strip(), _clean(v)
            if v and not env.get(k):
                env[k] = v
    for k, v in os.environ.items():
        if k.startswith(("GORGIAS_", "SHOPIFY_", "REDO_")) and v.strip():
            env[k] = v
    return env
