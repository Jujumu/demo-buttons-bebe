import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT=Path(__file__).parents[1]/'invalidate_hermes_mcp_cache.py'
spec=importlib.util.spec_from_file_location('invalidate',SCRIPT)
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

class CacheInvalidationTests(unittest.TestCase):
    def test_only_named_servers_removed_and_unknown_entries_preserved(self):
        data={name:{'tools':[{'name':'read','inputSchema':{}}]} for name in module.SERVERS}
        data['unrelated']={'opaque':['retain',{'nested':True}]}
        desired,names=module.invalidate(json.dumps(data).encode())
        self.assertEqual(json.loads(desired),{'unrelated':data['unrelated']})
        self.assertEqual(set(names),module.SERVERS)
        self.assertEqual(module.invalidate(desired),(desired,[]))
        with self.assertRaises(ValueError):module.invalidate(b'[]')
    def test_apply_requires_hash_and_backs_up_exact_raw_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);cache=root/'cache';backup=root/'backup'
            raw=b'{ "buttonsbebe_kb": {}, "other": {"preserve":true} }\n';cache.write_bytes(raw)
            command=[sys.executable,str(SCRIPT),str(cache)]
            self.assertEqual(subprocess.run(command,capture_output=True).returncode,0)
            self.assertEqual(cache.read_bytes(),raw)
            bad=subprocess.run(command+['--apply','--backup',str(backup),'--expected-sha256','bad'],capture_output=True)
            self.assertNotEqual(bad.returncode,0);self.assertFalse(backup.exists());self.assertEqual(cache.read_bytes(),raw)
            good=subprocess.run(command+['--apply','--backup',str(backup),'--expected-sha256',hashlib.sha256(raw).hexdigest()],capture_output=True)
            self.assertEqual(good.returncode,0,good.stderr)
            self.assertEqual(backup.read_bytes(),raw)
            self.assertEqual(json.loads(cache.read_bytes()),{'other':{'preserve':True}})
