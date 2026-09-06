"""Authenticated console actions reject empty text before any external write."""
import unittest
from unittest.mock import patch
from bb_webhook import app as app_module
from webhook.action_test_support import setup_action_case

class ConsoleActionsRequireTextTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        await setup_action_case(self)

    async def test_send_and_note_reject_empty_text_with_400(self):
        with patch.object(app_module, '_GClient') as transport:
            send = await self.client.post('/dashboard/api/ticket/1/send', json={'text':'   ', 'confirmed': True})
            note = await self.client.post('/dashboard/api/ticket/1/note', json={'text':'', 'confirmed': True})
        self.assertEqual(send.status_code, 400)
        self.assertEqual(send.json(), {'error':'empty reply'})
        self.assertEqual(note.status_code, 400)
        self.assertEqual(note.json(), {'error':'empty note'})
        transport.assert_not_called()
