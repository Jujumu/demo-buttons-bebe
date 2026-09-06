"""Transactional inbox state; independent of code releases and credentials.

One versioned snapshot keeps ticket, sequence and dedupe updates atomic. BEGIN
IMMEDIATE serializes processes; callers reload within the transaction before
mutating. This modest inbox does not need a second database server.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path


class StoreUnavailable(RuntimeError):
    """Persistent state must never be silently replaced by an empty inbox."""


def validate(state: dict) -> dict:
    if not isinstance(state, dict) or not isinstance(state.get("tickets"), list):
        raise StoreUnavailable("Inbox state has an invalid ticket collection")
    ids = set()
    for row in state["tickets"]:
        if not isinstance(row, dict) or not isinstance(row.get("id"), str) or row["id"] in ids:
            raise StoreUnavailable("Inbox state has an invalid or duplicate ticket")
        ids.add(row["id"])
        for field in ("customerName", "subject", "snippet", "status", "updatedAt"):
            if not isinstance(row.get(field), str):
                raise StoreUnavailable("Inbox state has an invalid ticket field")
        if row["status"] not in ("open", "closed", "snoozed"):
            raise StoreUnavailable("Inbox state has an invalid ticket status")
        if not isinstance(row.get("messages"), list) or not isinstance(row.get("statusEvents"), list):
            raise StoreUnavailable("Inbox state has invalid ticket history")
        if any(not isinstance(item, dict) for item in row["messages"] + row["statusEvents"]):
            raise StoreUnavailable("Inbox state has invalid ticket history entries")
    if not isinstance(state.get("seen", []), list) or any(not isinstance(x, str) for x in state.get("seen", [])):
        raise StoreUnavailable("Inbox state has invalid deduplication data")
    if not isinstance(state.get("dedupe", []), list):
        raise StoreUnavailable("Inbox state has invalid ticket deduplication data")
    for entry in state.get("dedupe", []):
        if not isinstance(entry, dict) or not isinstance(entry.get("key"), list) or entry.get("ticketId") not in ids:
            raise StoreUnavailable("Inbox state has invalid ticket deduplication data")
    if not isinstance(state.get("nextSeq", 1), int) or state.get("nextSeq", 1) < 1:
        raise StoreUnavailable("Inbox state has an invalid sequence")
    return state


def connect(path: Path) -> sqlite3.Connection:
    try:
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        db = sqlite3.connect(path, timeout=10, isolation_level=None)
        db.execute("PRAGMA busy_timeout=10000")
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA synchronous=FULL")
        db.execute("CREATE TABLE IF NOT EXISTS inbox_state (id INTEGER PRIMARY KEY CHECK(id=1), version INTEGER NOT NULL, payload TEXT NOT NULL)")
        return db
    except (OSError, sqlite3.Error) as exc:
        raise StoreUnavailable("Inbox storage is unavailable; existing data was not reset") from exc


def read(db: sqlite3.Connection) -> dict | None:
    try:
        row = db.execute("SELECT version,payload FROM inbox_state WHERE id=1").fetchone()
        if row is None:
            return None
        if row[0] != 1:
            raise StoreUnavailable("Unsupported inbox storage version")
        return validate(json.loads(row[1]))
    except (sqlite3.Error, ValueError, TypeError) as exc:
        raise StoreUnavailable("Inbox storage is unreadable; existing data was not reset") from exc


def write(db: sqlite3.Connection, state: dict) -> None:
    validate(state)
    db.execute("INSERT INTO inbox_state(id,version,payload) VALUES(1,1,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload", (json.dumps(state, ensure_ascii=False),))
