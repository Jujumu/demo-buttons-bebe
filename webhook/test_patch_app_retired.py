"""The former live-file patcher must stay a harmless no-op."""

from __future__ import annotations

import contextlib
import io
import unittest
from pathlib import Path

from deploy import patch_app


class RetiredPatchAppTests(unittest.TestCase):
    def test_legacy_command_is_a_noop_and_has_no_literal_route_patcher(self) -> None:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = patch_app.main()

        self.assertEqual(result, 0)
        self.assertIn("retired", output.getvalue())
        source = Path(patch_app.__file__).read_text(encoding="utf-8")
        self.assertNotIn("sys.path.insert", source)
        self.assertNotIn("ANCHOR =", source)


if __name__ == "__main__":
    unittest.main()
