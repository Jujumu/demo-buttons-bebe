"""Private candidate validation, rollback, and actual Caddy temporary route gate."""
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import unittest
import urllib.request
import urllib.error
from test_inbox_caddy_contract import port

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('rewrite_maintenance', ROOT / 'tools/ops/rewrite_maintenance.py')
ops = importlib.util.module_from_spec(spec); spec.loader.exec_module(ops)
SOURCE = ROOT / 'deploy/caddy/sites/support.caddy'


class MaintenanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'sites').mkdir()
        self.entry = self.root / 'Caddyfile'
        self.entry.write_text('\n'.join('import sites/' + n + '.caddy' for n in ops.IMPORTS))
        for n in ops.IMPORTS:
            (self.root / 'sites' / (n + '.caddy')).write_text(SOURCE.read_text() if n == 'support' else '# synthetic\n')
        self.target = self.root / 'sites/support.caddy'; self.original = self.target.read_bytes()

    def apply(self, mode='install', command=lambda args: None):
        return ops.apply(mode, ops.digest(self.target.read_bytes()), self.entry, self.root / 'backups', command)

    def test_install_remove_exact_restore_and_private_backup(self):
        first = self.apply()
        self.assertIn(ops.BLOCK.encode(), self.target.read_bytes())
        self.assertEqual(Path(first['backup']).stat().st_mode & 0o777, 0o700)
        self.assertEqual((Path(first['backup']) / 'support.before.caddy').stat().st_mode & 0o777, 0o600)
        self.apply('remove'); self.assertEqual(self.target.read_bytes(), self.original)

    def test_validation_failure_does_not_touch_live_source(self):
        def fail(args): raise RuntimeError('synthetic validation failure')
        with self.assertRaises(RuntimeError): self.apply(command=fail)
        self.assertEqual(self.target.read_bytes(), self.original)

    def test_reload_failure_revalidates_and_restores_original(self):
        calls = []
        def fail_once(args):
            calls.append(args[1])
            if calls.count('reload') == 1 and args[1] == 'reload': raise RuntimeError('synthetic')
        with self.assertRaisesRegex(RuntimeError, 'restored'): self.apply(command=fail_once)
        self.assertEqual(calls, ['validate', 'validate', 'reload', 'validate', 'reload'])
        self.assertEqual(self.target.read_bytes(), self.original)

    def test_remove_reload_failure_restores_gate(self):
        self.apply()
        installed = self.target.read_bytes()
        reloads = []
        def fail_once(args):
            if args[1] == 'reload':
                reloads.append(True)
                if len(reloads) == 1: raise RuntimeError('synthetic')
        with self.assertRaisesRegex(RuntimeError, 'restored'):
            self.apply('remove', command=fail_once)
        self.assertEqual(self.target.read_bytes(), installed)

    def test_hash_and_altered_gate_fail_closed(self):
        with self.assertRaises(ValueError):
            ops.apply('install', 'wrong', self.entry, self.root / 'backups')
        with self.assertRaises(ValueError): ops.transform(SOURCE.read_text(), 'remove')


@unittest.skipUnless(shutil.which('caddy'), 'Actual Caddy tested in Linux container')
class LinuxRouteTests(unittest.TestCase):
    def test_gate_precedes_console_proxy_and_leaves_other_routes_available(self):
        listen = port()
        # Use the exact inserted gate and same competing named console handler.
        transformed = ops.transform(SOURCE.read_text(), 'install')
        inserted = transformed.split(ops.ANCHOR, 1)[1].split('\t@whatsapp', 1)[0]
        with tempfile.TemporaryDirectory() as temp:
            config = Path(temp) / 'Caddyfile'
            config.write_text('{\n admin off\n auto_https off\n}\n'
                + f'http://support.buttonsbebe.com:{listen}, http://srv1766050.hstgr.cloud:{listen} {{\n'
                + inserted + '\n @consoleapi path /console/api/*\n handle @consoleapi {\n respond "console" 200\n }\n handle {\n respond "unchanged" 200\n }\n}\n')
            validated = subprocess.run(['caddy','validate','--config',str(config),'--adapter','caddyfile'],capture_output=True)
            self.assertEqual(validated.returncode, 0, validated.stderr)
            child = subprocess.Popen(['caddy','run','--config',str(config),'--adapter','caddyfile'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            try:
                for host in ('support.buttonsbebe.com','srv1766050.hstgr.cloud'):
                    for path, expected in [('/console/api/ticket/123/rewrite',503),('/console/api/ticket/123/rewrite/',503),
                            ('/console/api/ticket/123/send',200),('/console/api/auth/session',200),
                            ('/console/login',200),('/console/',200),('/webhook/gorgias/synthetic',200),
                            ('/console/api/ticket/123/rewrite-extra',200)]:
                        request = urllib.request.Request(f'http://127.0.0.1:{listen}'+path, data=b'{}', headers={'Host':host})
                        for attempt in range(60):
                            try:
                                with urllib.request.urlopen(request,timeout=2) as reply: status=reply.status
                                break
                            except urllib.error.HTTPError as error: status=error.code; break
                            except urllib.error.URLError:
                                if attempt == 59: raise
                                time.sleep(.05)
                        self.assertEqual(status,expected,(host,path))
            finally:
                child.terminate(); child.wait(timeout=5)
