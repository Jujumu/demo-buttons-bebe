"""Synthetic safety tests for reviewed operations scripts; never touch live paths."""
from __future__ import annotations
from datetime import datetime, timezone
from contextlib import closing
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/ops'))
import sqlite_backup
import scheduled_backup
import inbox_runtime


class BackupTests(unittest.TestCase):
    def test_wal_snapshot_is_consistent_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / 'live.db'
            reader = sqlite3.connect(source)
            self.addCleanup(reader.close)
            reader.execute('PRAGMA journal_mode=WAL')
            reader.execute('CREATE TABLE synthetic(value TEXT)')
            reader.execute("INSERT INTO synthetic VALUES ('committed')"); reader.commit()
            reader.execute("INSERT INTO synthetic VALUES ('uncommitted')")
            target = root / 'snapshot.sqlite3'
            receipt = sqlite_backup.backup(source, target)
            with closing(sqlite3.connect(target)) as snapshot:
                self.assertEqual(snapshot.execute('SELECT * FROM synthetic').fetchall(), [('committed',)])
            self.assertEqual(receipt['integrity'], 'ok')
            self.assertEqual(target.stat().st_mode & 0o777, 0o600)
            with self.assertRaises(ValueError): sqlite_backup.backup(source, target)
            reader.rollback()

    def test_invalid_database_never_produces_a_completed_backup(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / 'bad.db'; source.write_text('synthetic corruption')
            target = Path(temp) / 'snapshot.sqlite3'
            with self.assertRaises(sqlite3.DatabaseError): sqlite_backup.backup(source, target)
            self.assertFalse(target.exists())
            self.assertTrue(target.with_name(target.name + '.incomplete').exists())

    def test_retention_only_removes_old_verified_owned_snapshots_and_keeps_three(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            now = datetime.now(timezone.utc)
            manual = root / 'operator-backup.cms'; manual.write_bytes(b'keep')
            for n in range(1, 6):
                path = root / f'scheduled-2020010{n}T000000Z.cms'; path.write_bytes(b'synthetic encrypted bytes')
                path.with_suffix('.json').write_text(json.dumps({'ciphertext_sha256': hashlib.sha256(path.read_bytes()).hexdigest()}))
                os.utime(path, (1, 1))
            scheduled_backup.prune(root, now)
            self.assertTrue(manual.exists())
            self.assertEqual(len(list(root.glob('scheduled-*.cms'))), 3)

    def test_backup_failure_is_recorded_without_sensitive_exception_text(self):
        with tempfile.TemporaryDirectory() as temp:
            status = Path(temp) / 'backup-status.json'
            with patch.object(scheduled_backup, 'STATUS', status), patch.object(scheduled_backup, 'CERT', Path(temp) / 'missing.pem'):
                with self.assertRaises(RuntimeError): scheduled_backup.snapshot()
            record = json.loads(status.read_text())
            self.assertEqual(record['status'], 'failed')
            self.assertEqual(record['error_type'], 'FileNotFoundError')
            self.assertNotIn('missing.pem', status.read_text())

    def test_corrupt_prior_status_is_replaced_with_observable_failure(self):
        with tempfile.TemporaryDirectory() as temp:
            status = Path(temp) / 'backup-status.json'; status.write_text('not json')
            with patch.object(scheduled_backup, 'STATUS', status):
                with self.assertRaises(RuntimeError): scheduled_backup.snapshot()
            record = json.loads(status.read_text())
            self.assertEqual(record['status'], 'failed')
            self.assertEqual(record['error_type'], 'JSONDecodeError')


class InboxRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.runtime = self.root / 'inbox'; self.runtime.mkdir()
        (self.runtime / 'old-code').write_text('previous immutable code')
        self.stage = self.root / 'inbox-stage-test'; self.stage.mkdir()
        for tree in ('inbox', 'helpdesk-agent/helpdesk'):
            (self.stage / 'console-src' / tree).mkdir(parents=True)
        files = {'console-src/inbox/review_server.py':'from fastapi import FastAPI',
                 'console-src/inbox/static-manifest.json':'[]',
                 'console-src/inbox/requirements.txt':'fastapi==0.139.0\nuvicorn==0.50.2\n',
                 'console-src/inbox/requirements.lock':'synthetic locked requirements',
                 'console-src/helpdesk-agent/helpdesk/send_access.py':'SEND_ACCESS_ENABLED = False\n'}
        for name, content in files.items(): (self.stage / name).write_text(content)
        (self.stage / 'venv/bin').mkdir(parents=True)
        (self.stage / 'venv/bin/python').write_text('synthetic prepared binary')
        (self.stage / 'prepared.json').write_text(json.dumps({'source_files':{name:inbox_runtime.digest(self.stage/name) for name in files},
            'requirements':inbox_runtime.digest(self.stage/'console-src/inbox/requirements.lock'),'dependencies':[]}))
        self.unit = self.root / 'installed.service'; self.unit.write_text('original unit')
        self.newunit = self.root / 'helpdesk-inbox.service'; self.newunit.write_text('User=bb-inbox\nProtectHome=true\n')
        self.backups = self.root / 'backups'
        self.state = self.root / 'state'; self.state.mkdir()
        (self.state / 'inbox.sqlite3').write_bytes(b'preserve every customer record')
        self.patches = [patch.object(inbox_runtime, name, value) for name,value in
                        [('RUNTIME',self.runtime),('UNIT',self.unit),('BACKUPS',self.backups),('STATE',self.state)]]
        self.patches.extend([patch.object(inbox_runtime,'owned_directory'),patch.object(inbox_runtime,'ensure_identity')])
        for mock in self.patches: mock.start(); self.addCleanup(mock.stop)
        self.calls = []
        def run(*args):
            self.calls.append(args)
            return 'active\n' if args[:2] == ('systemctl','show') else ''
        mock = patch.object(inbox_runtime,'run',side_effect=run);mock.start();self.addCleanup(mock.stop)

    def test_apply_and_idempotent_rollback_preserve_data_and_other_services(self):
        with patch.object(inbox_runtime,'probe'):
            inbox_runtime.apply(self.stage,self.newunit,inbox_runtime.digest(self.unit),True)
            self.assertTrue((self.runtime/'console-src/inbox/review_server.py').exists())
            backup = next(self.backups.iterdir())
            inbox_runtime.rollback(backup)
            before = len(self.calls)
            inbox_runtime.rollback(backup)
            self.assertEqual(len(self.calls), before)
        self.assertEqual(self.unit.read_text(),'original unit')
        self.assertTrue((self.runtime/'old-code').exists())
        self.assertEqual((self.state/'inbox.sqlite3').read_bytes(),b'preserve every customer record')
        for call in self.calls:
            if call[:2] in [('systemctl','start'),('systemctl','stop')]:
                self.assertEqual(call[2],'helpdesk-inbox.service')

    def test_failed_probe_restores_previous_code_and_unit_without_rewinding_data(self):
        with patch.object(inbox_runtime,'probe',side_effect=[RuntimeError('synthetic locked probe failure'),None]):
            with self.assertRaises(RuntimeError): inbox_runtime.apply(self.stage,self.newunit,inbox_runtime.digest(self.unit),True)
        self.assertEqual(self.unit.read_text(),'original unit')
        self.assertTrue((self.runtime/'old-code').exists())
        self.assertEqual((self.state/'inbox.sqlite3').read_bytes(),b'preserve every customer record')

    def test_concurrent_unit_change_and_unverified_state_refuse_before_stop(self):
        for expected,state in [('bad-sha',True),(inbox_runtime.digest(self.unit),False)]:
            with self.assertRaises(ValueError): inbox_runtime.apply(self.stage,self.newunit,expected,state)
        self.assertFalse(any(call[:2] == ('systemctl','stop') for call in self.calls))

    def test_modified_prepared_source_is_not_applied(self):
        (self.stage/'console-src/inbox/review_server.py').write_text('unreviewed')
        with self.assertRaises(ValueError): inbox_runtime.verify_stage(self.stage)
        self.assertEqual(self.calls,[])

    def test_dependency_drift_refuses_before_service_stop(self):
        with patch.object(inbox_runtime, 'run', return_value='unexpected-package==1\n'):
            with self.assertRaises(ValueError): inbox_runtime.verify_stage(self.stage)
        self.assertFalse(any(call[:2] == ('systemctl','stop') for call in self.calls))


if __name__ == '__main__': unittest.main()
