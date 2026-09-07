import importlib.util
from pathlib import Path
import tempfile
import unittest
spec = importlib.util.spec_from_file_location('check_inbox_locks', Path(__file__).with_name('check_inbox_locks.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class InboxLockTests(unittest.TestCase):
    def test_test_only_packages_do_not_change_runtime_pins(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root/'runtime').write_text('fastapi==1.0 \\\n --hash=sha256:abcd\n')
            (root/'tests').write_text('fastapi==1.0 --hash=sha256:abcd\nhttpx==2.0 --hash=sha256:abcd\n')
            self.assertEqual(module.check(root/'runtime', root/'tests'), 1)
            (root/'tests').write_text('fastapi==2.0 --hash=sha256:abcd\n')
            with self.assertRaisesRegex(ValueError, 'mismatch'):
                module.check(root/'runtime', root/'tests')

    def test_unpinned_unhashed_empty_and_duplicate_locks_fail(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/'lock'
            for text in ('', 'fastapi>=1\n', 'fastapi==1\n', 'fastapi==1 --hash=sha256:a\nfastapi==1 --hash=sha256:b\n'):
                path.write_text(text)
                with self.assertRaises(ValueError):
                    module.pins(path)
