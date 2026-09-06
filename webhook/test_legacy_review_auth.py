import unittest
from unittest.mock import Mock,patch
from bb_webhook.routers import console
from webhook.action_test_support import setup_action_case

class LegacyReviewTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):await setup_action_case(self)
    async def test_exact_confirmation_and_object_shape(self):
        reviewer=Mock()
        with patch.object(console,'_review',reviewer):
            for body in ([],None,{'pii_cleared':'false'},{'pii_cleared':1},{'pii_cleared':True,'note':[]},{'pii_cleared':True,'delivery_status':'sent'}):
                response=await self.client.post('/dashboard/api/review/approve/123',json=body)
                self.assertEqual(response.status_code,400)
        reviewer.approve.assert_not_called()
    async def test_owner_identity_is_bound_to_pii_review_only(self):
        reviewer=Mock();reviewer.approve.return_value={'ok':True,'next':'needs final edit'}
        with patch.object(console,'_review',reviewer):
            response=await self.client.post('/dashboard/api/review/approve/123',json={'pii_cleared':True,'note':'Reviewed'})
        self.assertEqual(response.status_code,200)
        reviewer.approve.assert_called_once_with('123',pii_cleared=True,note='Reviewed',why='',review_actor='owner:owner')
        self.assertNotIn('delivery_status',response.json())

class LegacyReviewPacketTests(unittest.TestCase):
    def test_packet_paths_reject_traversal_and_symlinks(self):
        import tempfile
        from pathlib import Path
        from feedback import review
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'private.md').write_text('private synthetic value')
            (root/'ticket-123.md').symlink_to(root/'private.md')
            with patch.object(review.config,'LEARNED_DIR',root):
                self.assertIsNone(review.get_packet('123'))
                self.assertIsNone(review.get_packet('../private'))
                self.assertFalse(review.reject('../private')['ok'])
            self.assertEqual((root/'private.md').read_text(),'private synthetic value')

    def test_pii_review_creates_only_unconfirmed_exemplar_with_actor(self):
        import tempfile
        from pathlib import Path
        from feedback import review
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);learned=root/'learned';learned.mkdir()
            (learned/'ticket-123.md').write_text('---\nreview_pending: true\n---\n## Customer situation\nA sizing question\n## Human reply as sent\nPlease consult the size chart.\n')
            with patch.object(review.config,'LEARNED_DIR',learned),patch.object(review.config,'TICKETS_DIR',root/'tickets'),patch.object(review.config,'ARCHIVE_DIR',root/'archive'):
                self.assertFalse(review.approve('123','false')['ok'])
                result=review.approve('123',True,review_actor='owner:owner')
                content=Path(result['exemplar']).read_text()
                self.assertIn('status: needs_final_edit',content)
                self.assertIn('pii_review_actor: owner:owner',content)
                self.assertNotIn('delivery_status:',content)
                self.assertNotIn('learning_approved:',content)
