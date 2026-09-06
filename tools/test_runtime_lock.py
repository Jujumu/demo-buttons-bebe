import unittest
import tempfile
from pathlib import Path
from tools.verify_runtime_lock import verify, verify_manifests

class RuntimeLockTests(unittest.TestCase):
    def test_exact_normalized_receipt_ignores_installer_only(self):
        self.assertEqual(verify('mcp==1.26.0 \\\n --hash=sha256:abc\nPyYAML==6.0.3\n', {'MCP':'1.26.0','pyyaml':'6.0.3','pip':'1'}), {'mcp':'1.26.0','pyyaml':'6.0.3'})
    def test_missing_extra_changed_and_empty_fail(self):
        for lock, installed in [('mcp==1.26.0', {}), ('mcp==1.26.0', {'mcp':'2.0.0'}),
                                ('mcp==1.26.0', {'mcp':'1.26.0','extra':'1'}), ('', {})]:
            with self.subTest(installed=installed), self.assertRaises(ValueError): verify(lock, installed)

    def test_changed_direct_pin_requires_reviewed_lock_update(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ('requirements.lock', 'runtime-constraints.txt', 'requirements.txt'):
                (root/name).write_text('mcp==1.26.0\n')
            verify_manifests(root/'requirements.lock')
            (root/'requirements.txt').write_text('mcp==2.0.0\n')
            with self.assertRaises(ValueError): verify_manifests(root/'requirements.lock')
