"""Contract tests for the first-party Python file-size guard.

The helper is intentionally kept separate from this test module.  These tests
exercise its supported scan-root CLI::

    bash tools/check_python_file_sizes.sh ROOT [ROOT ...]

The helper uses a fixed 1,000-line limit, reports every offending production
file, and exits non-zero for invalid roots or for a root set with no production
Python files.  With no arguments it requires and scans the repository's
processor, webhook, and kb roots.  All test inputs are local temporary
directories; the subprocess is never given a shell command string.
"""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
HELPER = Path(__file__).with_name("check_python_file_sizes.sh").resolve()


class PythonFileSizeGuardTests(unittest.TestCase):
    def setUp(self) -> None:
        if not HELPER.is_file():
            self.fail(
                "expected helper is missing; implement the documented CLI first: "
                f"{HELPER}"
            )

    @staticmethod
    def write_lines(root: Path, relative_path: str, line_count: int) -> Path:
        path = root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("x\n" * line_count, encoding="utf-8")
        return path

    @staticmethod
    def run_checker(*roots: Path) -> subprocess.CompletedProcess[str]:
        environment = os.environ.copy()
        environment.update({"LANG": "C", "LC_ALL": "C"})
        return subprocess.run(
            ["bash", str(HELPER), *(str(root) for root in roots)],
            cwd=REPO_ROOT,
            env=environment,
            capture_output=True,
            check=False,
            text=True,
        )

    @staticmethod
    def output(result: subprocess.CompletedProcess[str]) -> str:
        return result.stdout + result.stderr

    def test_exactly_one_thousand_production_lines_pass(self) -> None:
        with tempfile.TemporaryDirectory(prefix="tfix5-size-guard-") as temp_dir:
            root = Path(temp_dir) / "production"
            file_path = self.write_lines(root, "module.py", 1000)

            result = self.run_checker(root)

            self.assertEqual(result.returncode, 0, self.output(result))
            self.assertNotIn(str(file_path), self.output(result))

    def test_one_thousand_and_one_production_lines_fail(self) -> None:
        with tempfile.TemporaryDirectory(prefix="tfix5-size-guard-") as temp_dir:
            root = Path(temp_dir) / "production"
            file_path = self.write_lines(root, "module.py", 1001)

            result = self.run_checker(root)
            output = self.output(result)

            self.assertNotEqual(result.returncode, 0, output)
            self.assertIn(str(file_path), output)
            self.assertIn("1001", output)

    def test_multiple_offenders_are_all_reported(self) -> None:
        with tempfile.TemporaryDirectory(prefix="tfix5-size-guard-") as temp_dir:
            root = Path(temp_dir) / "production"
            offenders = [
                self.write_lines(root, "first.py", 1001),
                self.write_lines(root, "nested/second.py", 1002),
                self.write_lines(root, "third.py", 1200),
            ]

            result = self.run_checker(root)
            output = self.output(result)

            self.assertNotEqual(result.returncode, 0, output)
            for offender in offenders:
                with self.subTest(offender=offender):
                    self.assertIn(str(offender), output)

    def test_excluded_paths_do_not_count_as_production_files(self) -> None:
        with tempfile.TemporaryDirectory(prefix="tfix5-size-guard-") as temp_dir:
            root = Path(temp_dir) / "production"
            self.write_lines(root, "kept.py", 1)
            excluded_paths = [
                "test_fixture.py",
                "helper_test.py",
                "tests/test_fixture.py",
                "nested/tests/test_fixture.py",
                ".venv/lib/python3.12/site-packages/fixture.py",
                "venv/lib/fixture.py",
                "site-packages/fixture.py",
                "node_modules/package/fixture.py",
                "__pycache__/fixture.py",
                "build/fixture.py",
                "dist/fixture.py",
                "generated/fixture.py",
                "index/fixture.py",
                "cache/fixture.py",
            ]
            for relative_path in excluded_paths:
                self.write_lines(root, relative_path, 1001)

            result = self.run_checker(root)

            self.assertEqual(result.returncode, 0, self.output(result))

    def test_production_packages_with_generated_sounding_names_are_scanned(self) -> None:
        with tempfile.TemporaryDirectory(prefix="tfix5-size-guard-") as temp_dir:
            root = Path(temp_dir) / "production"
            self.write_lines(root, "kept.py", 1)
            offenders = [
                self.write_lines(root, "domain/data/overlong.py", 1001),
                self.write_lines(root, "domain/index/overlong.py", 1001),
                self.write_lines(root, "domain/cache/overlong.py", 1001),
                self.write_lines(root, "domain/generated/overlong.py", 1001),
            ]

            result = self.run_checker(root)
            output = self.output(result)

            self.assertNotEqual(result.returncode, 0, output)
            for offender in offenders:
                with self.subTest(offender=offender):
                    self.assertIn(str(offender), output)

    def test_missing_root_fails(self) -> None:
        with tempfile.TemporaryDirectory(prefix="tfix5-size-guard-") as temp_dir:
            missing_root = Path(temp_dir) / "missing root"

            result = self.run_checker(missing_root)
            output = self.output(result)

            self.assertNotEqual(result.returncode, 0, output)
            self.assertIn(str(missing_root), output)

    def test_default_scan_requires_all_three_production_roots(self) -> None:
        with tempfile.TemporaryDirectory(prefix="tfix5-size-guard-") as temp_dir:
            repository = Path(temp_dir) / "repository"
            tools_dir = repository / "tools"
            tools_dir.mkdir(parents=True)
            copied_helper = tools_dir / HELPER.name
            shutil.copy2(HELPER, copied_helper)
            (repository / "processor").mkdir()
            (repository / "webhook").mkdir()

            result = subprocess.run(
                ["bash", str(copied_helper)],
                cwd=repository,
                env=os.environ.copy(),
                capture_output=True,
                check=False,
                text=True,
            )
            output = self.output(result)

            self.assertNotEqual(result.returncode, 0, output)
            self.assertIn(str(repository / "kb"), output)

    def test_traversal_failure_is_not_treated_as_a_clean_scan(self) -> None:
        with tempfile.TemporaryDirectory(prefix="tfix5-size-guard-") as temp_dir:
            root = Path(temp_dir) / "production"
            self.write_lines(root, "kept.py", 1)
            fake_bin = Path(temp_dir) / "fake-bin"
            fake_bin.mkdir()
            fake_find = fake_bin / "find"
            fake_find.write_text("#!/bin/sh\nexit 23\n", encoding="utf-8")
            fake_find.chmod(fake_find.stat().st_mode | stat.S_IXUSR)
            environment = os.environ.copy()
            environment["PATH"] = f"{fake_bin}:{environment['PATH']}"

            result = subprocess.run(
                ["bash", str(HELPER), str(root)],
                cwd=REPO_ROOT,
                env=environment,
                capture_output=True,
                check=False,
                text=True,
            )
            output = self.output(result)

            self.assertNotEqual(result.returncode, 0, output)
            self.assertIn("traversal failed", output)

    def test_zero_production_files_fails(self) -> None:
        with tempfile.TemporaryDirectory(prefix="tfix5-size-guard-") as temp_dir:
            root = Path(temp_dir) / "empty-production"
            root.mkdir()
            (root / "README.md").write_text("fixture\n", encoding="utf-8")
            self.write_lines(root, "tests/only_fixture.py", 1)

            result = self.run_checker(root)

            self.assertNotEqual(result.returncode, 0, self.output(result))

    def test_root_and_filename_with_spaces_work(self) -> None:
        with tempfile.TemporaryDirectory(prefix="tfix5-size-guard-") as temp_dir:
            root = Path(temp_dir) / "root with spaces"
            file_path = self.write_lines(root, "production file.py", 1000)

            result = self.run_checker(root)

            self.assertEqual(result.returncode, 0, self.output(result))
            self.assertNotIn(str(file_path), self.output(result))


if __name__ == "__main__":
    unittest.main()
