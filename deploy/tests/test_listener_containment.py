"""Fault injection tests for narrow listener containment; no live commands."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools/ops'))
import contain_listeners as target


class ListenerContainmentTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.source=self.root/'server.js';self.source.write_text('const x=1;\nserver.listen(cfg.PORT, () => {\n});\n')
        self.unit=self.root/'exchange-proxy.service';self.unit.write_text('[Service]\nExecStart=/usr/bin/node server.js\n')
        self.info={'pid':123,'ticks':'456','unit':self.unit,'source':self.source}
        for mocked in (patch.object(target,'BACKUPS',self.root/'backups'),patch.object(target,'service_info',return_value=self.info)):
            mocked.start();self.addCleanup(mocked.stop)

    def apply(self):target.apply('exchange',123,'456',target.sha(self.unit),target.sha(self.source))

    def test_exact_bind_only_and_refuses_ambiguous_expression(self):
        original=self.source.read_text();changed=target.rewrite('exchange',original)
        self.assertEqual(changed.replace(', "127.0.0.1"',''),original)
        with self.assertRaises(ValueError):target.rewrite('exchange',original+original)
        with self.assertRaises(ValueError):target.rewrite('exchange',changed)
        unit='[Service]\nExecStart=/usr/bin/python -m app --host 0.0.0.0 --port 9119\n'
        self.assertEqual(target.rewrite('hermes',unit).replace('127.0.0.1','0.0.0.0'),unit)
        with self.assertRaises(ValueError):target.rewrite('hermes','# --host 0.0.0.0\n')

    def test_proxy_failure_cannot_modify_source_or_restart(self):
        original=self.source.read_bytes()
        with patch.object(target,'probe',side_effect=RuntimeError),patch.object(target,'run') as command:
            with self.assertRaises(RuntimeError):self.apply()
            command.assert_not_called()
        self.assertEqual(self.source.read_bytes(),original)

    def test_identity_and_hash_guards_run_before_network(self):
        with patch.object(target,'probe') as probe:
            with self.assertRaises(ValueError):target.apply('exchange',123,'wrong',target.sha(self.unit),target.sha(self.source))
            with self.assertRaises(ValueError):target.apply('exchange',123,'456','wrong',target.sha(self.source))
            probe.assert_not_called()

    def test_concurrent_edit_during_probe_refuses_mutation(self):
        original=self.source.read_bytes()
        def probe(*args):
            self.unit.write_text('concurrent unit edit');return 200,'text/html'
        with patch.object(target,'probe',side_effect=probe),patch.object(target,'replace') as replace:
            with self.assertRaises(ValueError):self.apply()
            replace.assert_not_called()
        self.assertEqual(self.source.read_bytes(),original)

    def test_restart_failure_keeps_contained_source_and_private_backup(self):
        original=self.source.read_bytes()
        def command(*args):
            if args[:2]==('systemctl','restart'):raise RuntimeError('synthetic failure')
            return ''
        with patch.object(target,'probe',return_value=(200,'text/html')),patch.object(target,'run',side_effect=command):
            with self.assertRaises(RuntimeError):self.apply()
        self.assertIn('127.0.0.1',self.source.read_text())
        backup=next((self.root/'backups').iterdir())
        self.assertEqual(backup.stat().st_mode & 0o777,0o700)
        self.assertEqual((backup/'server.js').read_bytes(),original)

    def test_success_restarts_only_named_service_and_probes_both_boundaries(self):
        with patch.object(target,'probe',return_value=(200,'text/html')) as probe,patch.object(target,'run',return_value='') as command,patch.object(target,'listener',return_value=True):
            self.apply()
        self.assertEqual([call.args for call in command.call_args_list if call.args[0]=='systemctl'],[('systemctl','restart','exchange-proxy.service')])
        self.assertEqual(probe.call_count,4)
        self.assertIn('127.0.0.1',self.source.read_text())

    def test_listener_requires_only_expected_pid_on_only_local_addresses(self):
        for row,expected in [('LISTEN 0 5 127.0.0.1:4100 0.0.0.0:* users:(("node",pid=123,fd=1))',True),('LISTEN 0 5 *:4100 *:* users:(("node",pid=123,fd=1))',False),('LISTEN 0 5 127.0.0.1:4100 *:* users:(("node",pid=456,fd=1))',False)]:
            with patch.object(target,'run',return_value=row):self.assertEqual(target.listener(4100,123),expected)

    def test_preview_signals_only_validated_pidfd_and_rejects_live_directory(self):
        proc=self.root/'proc'/'123';proc.mkdir(parents=True)
        (proc/'cmdline').write_bytes(b'/usr/bin/python3\0-m\0http.server\08099\0')
        (proc/'cwd').symlink_to('/synthetic-preview (deleted)')
        def paths(value):return self.root/'proc' if str(value)=='/proc' else Path(value)
        row='LISTEN 0 5 *:8099 *:* users:(("python3",pid=123,fd=1))'
        with patch.object(target,'Path',side_effect=paths),patch.object(target,'identity',return_value='456'),patch.object(target,'run',side_effect=[row,'']),patch.object(target.os,'pidfd_open',return_value=999,create=True) as opened,patch.object(target.signal,'pidfd_send_signal',create=True) as send,patch.object(target.os,'close'):
            target.stop_preview(123,'456')
            opened.assert_called_once_with(123)
            send.assert_called_once_with(999,target.signal.SIGTERM)
        (proc/'cwd').unlink();(proc/'cwd').symlink_to('/synthetic-live-preview')
        with patch.object(target,'Path',side_effect=paths),patch.object(target,'identity',return_value='456'),patch.object(target.signal,'pidfd_send_signal',create=True) as send:
            with self.assertRaises(ValueError):target.stop_preview(123,'456')
            send.assert_not_called()

    def test_preview_identity_failure_never_signals(self):
        with patch.object(target,'identity',return_value='changed'),patch.object(target.signal,'pidfd_send_signal',create=True) as send:
            with self.assertRaises(ValueError):target.stop_preview(123,'456')
            send.assert_not_called()


if __name__=='__main__':unittest.main()
