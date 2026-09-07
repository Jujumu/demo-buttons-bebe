"""Production never presents demo records or falls back to test-store data."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from helpdesk import tickets
from helpdesk.dispatch import invoke

class ProductionInboxTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Path(self.tmp.name) / 'tickets.json'
        self.env = patch.dict(os.environ, {'HELPDESK_PRODUCTION':'1', 'HELPDESK_STORE_FILE':str(self.store), 'HELPDESK_SEEN_FILE':str(Path(self.tmp.name)/'seen.json')})
        self.env.start()
        tickets.reset()

    def tearDown(self):
        self.env.stop()
        tickets.reset()
        self.tmp.cleanup()

    def test_new_production_inbox_is_empty_and_seed_cannot_be_opened(self):
        result = invoke('helpdesk.list_tickets', {'view':'all'})
        self.assertEqual(result['tickets'], [])
        self.assertEqual(result['source'], 'inbox')
        self.assertEqual(invoke('helpdesk.get_ticket', {'ticketId':'t-ada-track'})['error'], 'not_found')

    def test_existing_intake_is_preserved_on_start(self):
        self.store.write_text(json.dumps({'tickets':[{'id':'t-in-400','customerName':'Test intake','subject':'Existing conversation','snippet':'Existing','status':'open','updatedAt':'2026-09-01T00:00:00Z','messages':[],'statusEvents':[],'source':'gorgias','joined':True}]}))
        before = self.store.read_bytes()
        tickets.reset()
        rows=invoke('helpdesk.list_tickets', {'view':'all'})['tickets']
        self.assertEqual([row['id'] for row in rows], ['t-in-400'])
        self.assertEqual(self.store.read_bytes(), before)

    def test_demo_generation_and_test_shop_are_unavailable(self):
        for tool in ('helpdesk.pull_mailbox','helpdesk.draft_reply','helpdesk.summarize_thread','helpdesk.search_macros'):
            self.assertEqual(invoke(tool, {'force':True,'ticketId':'t-ada-track'})['error'], 'integration_inactive')
        result=invoke('helpdesk.get_customer', {'shop':'demo-inbox.example','customerId':'gid://shopify/Customer/9001'})
        self.assertEqual(result['error'], 'integration_inactive')

    def test_send_still_locked_even_with_confirmed_true(self):
        result=invoke('helpdesk.send_reply', {'ticketId':'t-ada-track','text':'Hi','confirmed':True}, actor='human')
        self.assertEqual(result['error'], 'send_access_inactive')
        self.assertEqual(result['message'], 'Activate the send access.')
