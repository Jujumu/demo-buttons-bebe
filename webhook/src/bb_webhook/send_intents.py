"""Durable human action intents. SQLite records authority before any remote POST.

An ambiguous transport result is never retried by this module. A matching retry
returns the existing intent; only a stored remote message ID can be reconciled
with a read. An operator must inspect unidentifiable outcomes in Gorgias.
"""
from __future__ import annotations

import hashlib
import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .db import Database

_SCHEMA = '''CREATE TABLE IF NOT EXISTS console_action_intents (
 operation_id TEXT PRIMARY KEY, semantic_hash TEXT NOT NULL UNIQUE,
 actor_id TEXT NOT NULL, kind TEXT NOT NULL, ticket_id INTEGER NOT NULL,
 source_message_id TEXT NOT NULL, recipient TEXT NOT NULL, text_hash TEXT NOT NULL,
 approved_text TEXT NOT NULL, customer_message TEXT NOT NULL, ai_draft TEXT NOT NULL,
 draft_hash TEXT NOT NULL, approve_learning INTEGER NOT NULL DEFAULT 0,
 state TEXT NOT NULL, remote_message_id INTEGER, response_json TEXT NOT NULL,
 response_status INTEGER NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 learning_recorded INTEGER NOT NULL DEFAULT 0
)'''


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def valid_operation(value) -> bool:
    try:
        return isinstance(value, str) and str(uuid.UUID(value)) == value.lower() and len(value) == 36
    except (ValueError, AttributeError):
        return False


class ActionConflict(Exception):
    def __init__(self, error: str, status=409, operation_id=None):
        self.error, self.status, self.operation_id = error, status, operation_id
        super().__init__(error)


class IntentStore:
    def __init__(self, path: Path | str):
        self.db = Database(path)

    async def reserve(self, *, operation_id: str, actor_id: str, kind: str,
                      ticket_id: int, source_message_id: str, text: str, draft_revision: str,
                      approve_learning: bool = False) -> tuple[dict, bool]:
        if not valid_operation(operation_id):
            raise ActionConflict('valid_operation_id_required', 400)
        if not source_message_id or len(source_message_id) > 200:
            raise ActionConflict('source_message_id_required', 400)
        if not actor_id or kind not in {'send', 'note'}:
            raise ActionConflict('not_authenticated', 401)
        if not isinstance(draft_revision, str) or not re.fullmatch('[0-9a-f]{64}', draft_revision):
            raise ActionConflict('draft_revision_required', 400)
        text_hash = _hash(text)

        async def transaction(conn):
            await conn.execute(_SCHEMA)
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_console_action_pending ON console_action_intents(ticket_id,kind,state)")
            cursor = await conn.execute('SELECT * FROM console_action_intents WHERE operation_id=?', (operation_id,))
            existing = await cursor.fetchone()
            await cursor.close()
            if existing:
                row = dict(existing)
                for name, value in {'actor_id': actor_id, 'kind': kind, 'ticket_id': ticket_id,
                                    'source_message_id': source_message_id, 'text_hash': text_hash, 'draft_hash': draft_revision,
                                    'approve_learning': int(approve_learning)}.items():
                    if row[name] != value:
                        raise ActionConflict('operation_id_conflict')
                return row, False
            cursor = await conn.execute('''SELECT pm.customer_email, pm.message_text, tr.draft_text
                FROM parsed_messages pm LEFT JOIN ticket_results tr ON tr.ticket_id=pm.ticket_id AND tr.message_id=pm.message_id
                WHERE pm.ticket_id=? AND pm.message_id=? AND pm.is_customer_message=1''',
                (ticket_id, source_message_id))
            context = await cursor.fetchone()
            await cursor.close()
            if not context:
                raise ActionConflict('source_message_not_in_console', 404)
            recipient = (context['customer_email'] or '').strip().lower()
            if kind == 'send' and not recipient:
                raise ActionConflict('recipient_unavailable', 409)
            ai_draft = context['draft_text'] or ''
            if _hash(ai_draft) != draft_revision:
                raise ActionConflict('draft_changed_refresh_ticket')
            semantic = _hash(json.dumps([kind, ticket_id, source_message_id, recipient,
                                        _hash(ai_draft), text_hash], separators=(',', ':')))
            cursor = await conn.execute('SELECT * FROM console_action_intents WHERE semantic_hash=?', (semantic,))
            previous = await cursor.fetchone()
            await cursor.close()
            if previous:
                if previous['actor_id'] != actor_id:
                    raise ActionConflict('action_owned_by_another_actor', 403)
                if previous['approve_learning'] != int(approve_learning):
                    raise ActionConflict('learning_approval_is_fixed_for_existing_action', operation_id=previous['operation_id'])
                return dict(previous), False  # New browser tab/key, same reviewed message.
            cursor = await conn.execute('''SELECT operation_id FROM console_action_intents
                WHERE ticket_id=? AND kind=? AND state IN ('uncertain','pending') LIMIT 1''', (ticket_id, kind))
            unresolved = await cursor.fetchone()
            await cursor.close()
            if unresolved:
                raise ActionConflict('previous_delivery_unresolved', operation_id=unresolved['operation_id'])
            now = _now()
            response = {'ok': False, 'error': 'delivery_unconfirmed', 'delivery_status': 'unknown',
                        'operation_id': operation_id,
                        'message': 'Check this action status before sending again. No automatic resend.'}
            await conn.execute('''INSERT INTO console_action_intents
                (operation_id, semantic_hash, actor_id, kind, ticket_id, source_message_id,
                 recipient, text_hash, approved_text, customer_message, ai_draft, draft_hash,
                 approve_learning, state, response_json, response_status, created_at, updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,'uncertain',?,202,?,?)''',
                (operation_id, semantic, actor_id, kind, ticket_id, source_message_id, recipient,
                 text_hash, text, context['message_text'] or '', ai_draft, _hash(ai_draft),
                 int(approve_learning), json.dumps(response), now, now))
            cursor = await conn.execute('SELECT * FROM console_action_intents WHERE operation_id=?', (operation_id,))
            row = dict(await cursor.fetchone())
            await cursor.close()
            return row, True
        return await self.db.transaction(transaction, operation='reserve_console_action')

    async def get(self, operation_id: str) -> dict | None:
        await self.db.execute(_SCHEMA, operation='init_console_actions')
        rows = await self.db.fetch('SELECT * FROM console_action_intents WHERE operation_id=?', (operation_id,))
        return dict(rows[0]) if rows else None

    async def attach_message(self, operation_id: str, message_id: int):
        if type(message_id) is not int or message_id <= 0:
            raise ValueError('invalid remote message id')
        response = {'ok': True, 'delivery_status': 'pending', 'operation_id': operation_id,
                    'message_id': message_id}
        await self.db.execute('''UPDATE console_action_intents SET remote_message_id=?, state='pending',
            response_json=?, response_status=202, updated_at=? WHERE operation_id=? AND state='uncertain' ''',
            (message_id, json.dumps(response), _now(), operation_id), operation='record_remote_message')

    async def finish(self, operation_id: str, state: str, response: dict, status: int):
        if state not in {'sent', 'recorded', 'pending', 'uncertain', 'failed'}:
            raise ValueError('invalid action state')
        await self.db.execute('''UPDATE console_action_intents SET state=?, response_json=?,
            response_status=?, updated_at=? WHERE operation_id=? AND state NOT IN ('sent','recorded')''',
            (state, json.dumps(response), status, _now(), operation_id), operation='finish_console_action')
        return await self.get(operation_id)

    async def mark_learning_recorded(self, operation_id: str):
        await self.db.execute('UPDATE console_action_intents SET learning_recorded=1 WHERE operation_id=?',
                              (operation_id,), operation='learning_recorded')
