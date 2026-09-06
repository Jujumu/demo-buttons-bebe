"""Source guards and sequencing for receiving containment; no real PM2 or HTTP."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools/ops'))
import contain_receiving as target


class ContainmentTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.source=self.root/'server.js'
        self.original='const unrelated = 1;\napp.listen(PORT, () => {\n});\n'
        self.source.write_text(self.original)
        self.info={'pid':123,'start_ticks':'456','source':self.source}
        for mocked in (patch.object(target,'BACKUPS',self.root/'backups'),patch.object(target,'process',return_value=self.info)):
            mocked.start();self.addCleanup(mocked.stop)

    def test_bind_change_is_small_and_idempotent(self):
        changed=target.bind_local(self.original)
        self.assertEqual(changed.replace(target.NEW_BIND,target.OLD_BIND),self.original)
        self.assertEqual(target.bind_local(changed),changed)
        with self.assertRaises(ValueError):target.bind_local(self.original+self.original)

    def test_proxy_failure_leaves_original_source_and_process_untouched(self):
        with patch.object(target,'probe_proxy',side_effect=RuntimeError('synthetic auth failure')),patch.object(target,'run') as run:
            with self.assertRaises(RuntimeError):target.apply('receiving',123,'456',target.sha(self.source),self.root/'cookie')
            run.assert_not_called()
        self.assertEqual(self.source.read_text(),self.original)

    def test_source_or_process_guard_refuses_before_proxy_or_restart(self):
        with patch.object(target,'probe_proxy') as probe,patch.object(target,'run') as run:
            for ticks,checksum in [('wrong',target.sha(self.source)),('456','wrong')]:
                with self.assertRaises(ValueError):target.apply('receiving',123,ticks,checksum,self.root/'cookie')
            probe.assert_not_called();run.assert_not_called()

    def test_verified_proxy_precedes_single_named_restart_and_preserves_backup(self):
        events=[]
        with patch.object(target,'probe_proxy',side_effect=lambda *_:events.append('proxy')), \
             patch.object(target,'run',side_effect=lambda *args:events.append(args) or ''), \
             patch.object(target,'loopback_listener',return_value=True):
            target.apply('receiving',123,'456',target.sha(self.source),self.root/'cookie')
        self.assertEqual(events[0],'proxy')
        self.assertEqual([item for item in events if isinstance(item,tuple) and item[0]=='pm2'],[('pm2','restart','receiving')])
        backup=next((self.root/'backups').iterdir())
        self.assertEqual((backup/'server.js').read_text(),self.original)
        self.assertIn(target.NEW_BIND,self.source.read_text())
        with self.assertRaises(ValueError):target.rollback(backup,False)
        self.assertIn(target.NEW_BIND,self.source.read_text())


if __name__=='__main__':unittest.main()
