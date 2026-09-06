import unittest
from tools.gorgias_content import curate_message,curate_messages,curate_ticket

class GorgiasContentTests(unittest.TestCase):
    def test_retained_content_selected_and_original_metadata_preserved(self):
        message={'id':123,'body_text':None,'body_html':None,'stripped_text':'Retained reply','headers':None,'body_url':'https://archive.example/private'}
        result=curate_messages({'data':[message]})['data'][0]
        self.assertEqual(result['preferred_content'],'Retained reply')
        self.assertEqual(result['preferred_content_field'],'stripped_text')
        self.assertFalse(result['content_unavailable'])
        self.assertEqual(result['body_url'],message['body_url'])
        self.assertNotIn('preferred_content',message)
    def test_html_only_and_missing_content_are_explicit(self):
        result=curate_ticket({'messages':[{'stripped_html':'<p>Retained</p>','body_text':'Old thread'}]})
        self.assertEqual(result['messages'][0]['preferred_content_field'],'stripped_html')
        self.assertTrue(curate_message({'body_text':None,'headers':None,'body_url':'http://127.0.0.1/private'})['content_unavailable'])
