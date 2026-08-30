"""Read Shopify env. Never print values. Never persist tokens."""

from __future__ import annotations

import os
from pathlib import Path

_KEYS = (
    "SHOPIFY_SHOP",
    "SHOPIFY_CLIENT_ID",
    "SHOPIFY_CLIENT_SECRET",
    "SHOPIFY_API_VERSION",
    "SHOPIFY_MUTATIONS_ENABLED",
    "HELPDESK_SOURCE",
)


def _clean(value: str) -> str:
    return value.strip().strip("\"'").replace("\r", "")


def load_shopify_env() -> dict[str, str]:
    found: dict[str, str] = {}
    root = Path(__file__).resolve().parents[3]
    env_path = root / ".env"
    if env_path.is_file():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            text = line.strip()
            if not text or text.startswith("#") or "=" not in text:
                continue
            key, raw = text.split("=", 1)
            key, raw = key.strip(), _clean(raw)
            if key in _KEYS and raw and key not in found:
                found[key] = raw
    for key in _KEYS:
        override = os.environ.get(key, "").strip()
        if override:
            found[key] = _clean(override)
    return found


def mutations_enabled(env: dict[str, str] | None = None) -> bool:
    value = (env or load_shopify_env()).get("SHOPIFY_MUTATIONS_ENABLED", "0")
    return value.strip().lower() in {"1", "true", "yes", "on"}
