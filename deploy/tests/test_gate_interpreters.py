"""Relative prepared Python paths survive nested test working directories."""
from pathlib import Path
import subprocess
import tempfile
import unittest

GATE=Path(__file__).resolve().parents[2]/'tools/verify_release.sh'

class GateInterpreterTests(unittest.TestCase):
    def test_relative_venv_path_is_absolute_without_resolving_symlink(self):
        source=GATE.read_text();start=source.index('absolute_interpreter() {');end=source.index('\nPYTHON=',start)
        function=source[start:end]
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);(root/'prepared/bin').mkdir(parents=True);(root/'other').mkdir()
            (root/'real-python').write_text('#!/bin/sh\nprintf "%s" "$0"\n');(root/'real-python').chmod(0o755)
            (root/'prepared/bin/python').symlink_to(root/'real-python')
            script=function+'\nROOT_DIR="$1"\nselected="$(absolute_interpreter prepared/bin/python)"\ncd "$ROOT_DIR/other"\n"$selected"\n'
            result=subprocess.run(['bash','-c',script,'test',str(root)],capture_output=True,text=True,check=True)
            self.assertEqual(result.stdout,str(root/'prepared/bin/python'))
