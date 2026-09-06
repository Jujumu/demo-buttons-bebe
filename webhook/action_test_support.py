"""Synthetic authenticated action fixture; no external network or live DB."""
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import httpx
from bb_webhook import app as app_module, database, session_store
from bb_webhook.console_auth import build_session_token, session_claims
from bb_webhook.db import Database


async def setup_action_case(case):
    case.tmp = tempfile.TemporaryDirectory()
    case.addCleanup(case.tmp.cleanup)
    case.path = Path(case.tmp.name) / 'actions.sqlite3'
    await database.init_db(case.path)
    await session_store.initialize(case.path)
    case.settings = SimpleNamespace(db_path_absolute=case.path, console_session_secret='test-action-secret',
                                    console_username='owner', demo_mode=False)
    for target in ('bb_webhook.app.get_settings', 'bb_webhook.db.get_settings'):
        patched = patch(target, return_value=case.settings)
        patched.start()
        case.addCleanup(patched.stop)
    await Database(case.path).execute('''INSERT INTO parsed_messages
        (message_id,ticket_id,event_type,author_type,customer_email,message_text,is_customer_message,received_at)
        VALUES ('source-1',1,'ticket.message.created','customer','customer@example.com','Where is my parcel?',1,'now')''')
    await Database(case.path).execute("INSERT INTO ticket_results(ticket_id,message_id,draft_text,processed_at) VALUES(1,'source-1','I can help check that.','now')")
    token = build_session_token('owner', 'test-action-secret')
    await session_store.register(session_claims(token, 'test-action-secret'), case.path)
    case.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app_module.app),
        base_url='https://support.buttonsbebe.com', headers={'Origin': 'https://support.buttonsbebe.com'},
        cookies={'bb_console_session': token})
    case.addAsyncCleanup(case.client.aclose)
