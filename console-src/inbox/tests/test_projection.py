import importlib.util
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from export_projection import export
from projection import query, connect, ProjectionUnavailable

class ProjectionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.source=self.root/'source.db';self.dest=self.root/'projection.sqlite3';self.now=time.time()
        with sqlite3.connect(self.source) as db:
            db.execute('CREATE TABLE parsed_messages(ticket_id INTEGER,message_id TEXT,author_type TEXT,author_email TEXT,customer_email TEXT,ticket_subject TEXT,channel TEXT,created_at TEXT,received_at TEXT,is_customer_message INTEGER,message_text TEXT)')
            db.execute('CREATE TABLE ticket_results(ticket_id INTEGER,message_id TEXT,draft_text TEXT,priority TEXT,action TEXT,reason TEXT,processed_at TEXT)')
            db.execute("INSERT INTO parsed_messages VALUES(1,'m1','customer','qa@example.com','qa@example.com','<script>title</script>','email','2099-01-01','2099-01-01',1,?)",('<img onerror=alert(1)>'+('x'*21000),))
            db.execute("INSERT INTO ticket_results VALUES(1,'m1','Draft only','high','sensitive_draft','Review','2099-01-01')")
    def tearDown(self):self.tmp.cleanup()
    def test_readonly_partial_mapping_and_text_limits(self):
        before=self.source.read_bytes();export(self.source,self.dest,now=self.now)
        self.assertEqual(before,self.source.read_bytes())
        result=query('helpdesk.get_ticket',{'ticketId':'gorgias:1'},self.dest)
        ticket=result['ticket'];self.assertEqual(ticket['status'],'unknown')
        self.assertTrue(ticket['truncated']);self.assertEqual(len(ticket['messages'][0]['body']),20000)
        self.assertEqual(ticket['readonlyDraft'],'Draft only')
        self.assertFalse(result['projection']['stale'])
        db=connect(self.dest)
        try:
            with self.assertRaises(sqlite3.OperationalError):db.execute('DELETE FROM tickets')
        finally:db.close()
    def test_atomic_publish_old_readers_and_failed_export_keep_previous(self):
        export(self.source,self.dest,now=self.now)
        db=connect(self.dest);db.execute('BEGIN');db.execute('SELECT * FROM tickets').fetchall()
        export(self.source,self.dest,now=self.now+1)
        self.assertEqual(db.execute('SELECT COUNT(*) FROM tickets').fetchone()[0],1);db.close()
        old=self.dest.read_bytes()
        with patch('export_projection.extract',side_effect=sqlite3.OperationalError('private detail')):
            with self.assertRaises(sqlite3.OperationalError):export(self.source,self.dest)
        self.assertEqual(old,self.dest.read_bytes())
        self.assertTrue(query('helpdesk.projection_status',{},self.dest)['projection']['stale'])
        self.assertEqual(self.dest.with_suffix('.error').read_text(),'')
    def test_ticket_and_message_windows_are_bounded(self):
        with sqlite3.connect(self.source) as db:
            for number in range(2,503):
                db.execute("INSERT INTO parsed_messages VALUES(?,?,'customer','','','Subject','email','2099-01-01','2099-01-01',1,'Hello')",(number,f'm{number}'))
            for number in range(102):
                db.execute("INSERT INTO parsed_messages VALUES(1,?,'customer','','','Subject','email','2099-02-01','2099-02-01',1,'Hello')",(f'extra{number}',))
        meta=export(self.source,self.dest,now=self.now)
        self.assertEqual(meta['ticketCount'],500);self.assertTrue(meta['truncated'])
        ticket=query('helpdesk.get_ticket',{'ticketId':'gorgias:1'},self.dest)['ticket']
        self.assertEqual(len(ticket['messages']),100);self.assertTrue(ticket['truncated'])
        self.assertEqual(ticket['observedMessageCount'],103)

    def test_stale_schema_and_pagination(self):
        export(self.source,self.dest,now=self.now-181)
        self.assertTrue(query('helpdesk.projection_status',{},self.dest)['projection']['stale'])
        self.assertEqual(query('helpdesk.list_tickets',{'offset':1,'limit':1},self.dest)['tickets'],[])
        with sqlite3.connect(self.dest) as db:db.execute("UPDATE metadata SET payload='{}'")
        with self.assertRaises(ProjectionUnavailable):query('helpdesk.list_tickets',{},self.dest)

if __name__=='__main__':unittest.main()
