import unittest
import tempfile
from pathlib import Path
from tools.verify_runtime_lock import verify, verify_manifests, exact_pins

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

    def test_exact_manifest_comments_and_normalized_names(self):
        self.assertEqual(exact_pins('# comment\n\n PyYAML==6.0.3 \npython_dateutil==2.9.0.post0\n'),
                         {'pyyaml':'6.0.3','python-dateutil':'2.9.0.post0'})

    def test_unsupported_and_ambiguous_lines_fail_for_both_manifests(self):
        invalid = ('newpkg>=1', 'mcp>=2', 'newpkg', 'mcp==1.*',
                   'mcp @ https://example.invalid/mcp.whl', '-r another.txt',
                   '--index-url https://example.invalid/simple', '-e ./package',
                   'mcp[extra]==1.26.0', 'mcp==1.26.0; python_version>="3.12"',
                   'mcp==1.26.0 --hash=sha256:abc', 'mcp==1.26.0 # inline comment',
                   'mcp==1.26.0', 'MCP==2.0.0', 'python_dateutil==2.9.0.post0\npython-dateutil==2.9.0.post0')
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            base = 'mcp==1.26.0\nrequests==2.32.4\n'
            for name in ('requirements.lock', 'runtime-constraints.txt', 'requirements.txt'):
                (root/name).write_text(base)
            for target in ('requirements.txt', 'runtime-constraints.txt'):
                for line in invalid:
                    with self.subTest(target=target, line=line):
                        (root/target).write_text(base + line + '\n')
                        with self.assertRaises(ValueError): verify_manifests(root/'requirements.lock')
                        (root/target).write_text(base)
            (root/'requirements.txt').write_text('mcp>=2\nrequests==2.32.4\n')
            with self.assertRaises(ValueError): verify_manifests(root/'requirements.lock')
