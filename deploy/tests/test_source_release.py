"""Recovery tests use temporary synthetic data only; no VPS or service calls."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('source_release', Path(__file__).parents[1] / 'cd/source_release.py')
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)

class SourceRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.staged = self.root / 'staged'
        self.live = self.root / 'live'
        self.web = self.root / 'web'
        self.journal = self.root / 'journal'
        self.state = self.root / 'state.json'
        for component in release.COMPONENTS:
            (self.staged / component).mkdir(parents=True)
            self.write(self.staged / component / 'app.py', 'new code')
        self.write(self.staged / '.buttonsbebe-release.json', json.dumps({'generation': 10, 'commit': 'a' * 40}))
        for name in ('index.html', 'login.html'):
            self.write(self.staged / 'console-src' / name, 'new html')
        self.write(self.live / 'webhook/app.py', 'old code')

    def write(self, path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value)

    def prepare(self):
        return release.prepare(self.staged, self.live, self.web, self.journal, self.state)

    def test_failed_release_preserves_new_data_credentials_venv_and_unknown_files(self):
        paths = ['.env', 'webhook/data/webhook.db', 'webhook/.venv/bin/python',
                 'KB/lancedb/index', 'KB/policies/policy.md', 'KB/tickets/learned.md',
                 'whatsapp-connect/auth/session.json', 'console-src/inbox/data/tickets.json',
                 'tools/unknown-runtime-file']
        for path in paths:
            self.write(self.live / path, 'before')
        self.prepare()
        release.apply(self.journal)
        for path in paths:
            self.write(self.live / path, 'after accepted customer work')
        release.apply(self.journal, rollback=True)
        for path in paths:
            self.assertEqual((self.live / path).read_text(), 'after accepted customer work', path)
            self.assertFalse((self.journal / 'files/app' / path).exists())
        self.assertEqual((self.live / 'webhook/app.py').read_text(), 'old code')
        self.assertFalse((self.live / 'console-src/inbox/app.py').exists())

    def test_partial_apply_recovers_and_repeated_rollback_is_safe(self):
        journal = self.prepare()
        first = journal['changes'][0]
        target = release.target_path(first['key'], self.live, self.web)
        release.atomic_copy(self.staged / first['entry']['source'], target)
        release.apply(self.journal, rollback=True)
        release.apply(self.journal, rollback=True)
        self.assertEqual((self.live / 'webhook/app.py').read_text(), 'old code')

    def test_concurrent_code_edit_prevents_partial_rollback_overwrite(self):
        self.prepare()
        release.apply(self.journal)
        self.write(self.live / 'webhook/app.py', 'independent fix')
        with self.assertRaisesRegex(ValueError, 'concurrent code edit'):
            release.apply(self.journal, rollback=True)
        self.assertEqual((self.live / 'webhook/app.py').read_text(), 'independent fix')
        self.assertEqual((self.web / 'index.html').read_text(), 'new html')

    def test_tampered_staged_artifact_is_rejected(self):
        self.prepare()
        self.write(self.staged / 'console-src/index.html', 'tampered')
        with self.assertRaisesRegex(ValueError, 'checksum changed'):
            release.apply(self.journal)
        release.apply(self.journal, rollback=True)

    def test_symlink_target_is_rejected(self):
        outside = self.root / 'customer-data'
        outside.mkdir()
        self.live.mkdir(exist_ok=True)
        (self.live / 'console-src').symlink_to(outside)
        with self.assertRaisesRegex(ValueError, 'symlink'):
            self.prepare()

    def test_dependency_changes_fail_before_backup_or_service_stop(self):
        self.write(self.staged / 'webhook/uv.lock', 'changed dependency')
        with self.assertRaisesRegex(ValueError, 'dependency preparation required'):
            self.prepare()
        self.assertFalse(self.journal.exists())
        self.assertEqual((self.live / 'webhook/app.py').read_text(), 'old code')

    def test_success_manifest_owns_only_source_and_detects_later_drift(self):
        for source in ('kb/policies/policy.md', 'console-src/inbox/data/live.json', 'webhook/.env'):
            self.write(self.staged / source, 'never ship this')
        journal = self.prepare()
        self.assertNotIn('app/KB/policies/policy.md', journal['files'])
        self.assertNotIn('app/webhook/.env', journal['files'])
        release.apply(self.journal)
        release.atomic_json({'files': journal['files']}, self.state)
        self.write(self.live / 'webhook/app.py', 'unreviewed live drift')
        with self.assertRaisesRegex(ValueError, 'live code drift'):
            release.prepare(self.staged, self.live, self.web, self.root / 'next-journal', self.state)

    def test_shell_entrypoint_execute_permission_is_restored(self):
        self.write(self.staged / 'kb/sync-products.sh', '#!/bin/bash\nexit 0\n')
        (self.staged / 'kb/sync-products.sh').chmod(0o644)
        self.prepare()
        release.apply(self.journal)
        self.assertEqual((self.live / 'KB/sync-products.sh').stat().st_mode & 0o777, 0o755)

    def test_stale_workflow_generation_is_rejected(self):
        self.write(self.state, json.dumps({'files': {}, 'generation': 11, 'commit': 'b' * 40}))
        with self.assertRaisesRegex(ValueError, 'stale release'):
            self.prepare()
        self.assertFalse(self.journal.exists())

    def test_only_previously_managed_file_is_removed_and_can_be_restored(self):
        journal = self.prepare()
        release.apply(self.journal)
        release.atomic_json({'files': journal['files']}, self.state)
        (self.staged / 'webhook/app.py').unlink()
        self.write(self.live / 'webhook/unknown.py', 'runtime custom')
        next_journal = self.root / 'second'
        release.prepare(self.staged, self.live, self.web, next_journal, self.state)
        release.apply(next_journal)
        self.assertFalse((self.live / 'webhook/app.py').exists())
        self.assertEqual((self.live / 'webhook/unknown.py').read_text(), 'runtime custom')
        release.apply(next_journal, rollback=True)
        self.assertEqual((self.live / 'webhook/app.py').read_text(), 'new code')

if __name__ == '__main__':
    unittest.main()
