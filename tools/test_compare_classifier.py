from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import tools.compare_classifier as harness


class CompareClassifierTests(unittest.TestCase):
    def test_release_gate_wires_fixed_plan_command(self) -> None:
        release_gate = (Path(__file__).resolve().parent / "verify_release.sh").read_text(
            encoding="utf-8"
        )
        self.assertIn("tools.test_compare_classifier", release_gate)
        self.assertIn("tools/compare_classifier.py", release_gate)
        self.assertIn("processor/classifier/__init__.py", release_gate)
        self.assertIn("--samples 10000", release_gate)
        self.assertIn("classifier parity skipped (T-FIX-3 package not present)", release_gate)

        parsed = harness._parser().parse_args(["--old", "old.py", "--new", "new.py"])
        self.assertEqual(parsed.samples, 10_000)

    def test_python_ci_fetches_history_for_the_parity_source(self) -> None:
        workflow = (
            Path(__file__).resolve().parents[1] / ".github" / "workflows" / "ci.yml"
        ).read_text(encoding="utf-8")
        python_job = workflow.split("  whatsapp:", 1)[0]
        self.assertIn("fetch-depth: 0", python_job)

    def test_synthetic_corpus_is_reproducible_and_exactly_sized(self) -> None:
        first = harness.synthetic_payloads(10_000, seed=17)
        second = harness.synthetic_payloads(10_000, seed=17)
        self.assertEqual(first, second)
        self.assertEqual(len(first), 10_000)
        self.assertTrue(all(payload[0]["synthetic"] for payload in first))
        self.assertTrue(all("example.test" in payload[0]["customer_email"] for payload in first))

    def test_shim_resolution_selects_newest_non_shim_history_source(self) -> None:
        shim = "from classifier import classify\n"
        old_impl = "def classify(payload, kb_results=None):\n    return {}\n"
        with tempfile.TemporaryDirectory(prefix="classifier-history-test-") as temp_name:
            root = Path(temp_name)
            old_path = root / "processor" / "classifier.py"
            old_path.parent.mkdir()
            old_path.write_text(shim, encoding="utf-8")
            materialize = root / "materialized"
            materialize.mkdir()

            def fake_git(_repo: Path, args: list[str]) -> str:
                if args[0] == "log":
                    return "newest\nolder\n"
                ref = args[-1]
                return shim if ref.startswith("newest:") else old_impl

            with patch.object(harness, "_run_git", side_effect=fake_git) as run_git:
                source = harness.resolve_old_source(old_path, root, materialize)

            self.assertEqual(source.origin, "Git older:processor/classifier.py")
            self.assertEqual(source.path.read_text(encoding="utf-8"), old_impl)
            self.assertEqual(run_git.call_count, 3)

    def test_two_isolated_engines_compare_exact_tuple(self) -> None:
        old_source = """
def classify(payload, kb_results=None):
    message = payload.get("message_text", "").lower()
    sensitive = bool(kb_results and any(item.get("sensitive") for item in kb_results))
    urgent = sensitive or "refund" in message
    return {
        "priority": "immediate" if urgent else "normal",
        "sensitive": urgent,
        "should_notify_owner": urgent,
    }
"""
        new_source = """
def classify(payload, kb_results=None):
    message = payload.get("message_text", "").lower()
    sensitive = bool(kb_results and any(item.get("sensitive") for item in kb_results))
    urgent = sensitive or "refund" in message
    return {
        "priority": "immediate" if urgent else "normal",
        "sensitive": urgent,
        "should_notify_owner": urgent,
    }
"""
        with tempfile.TemporaryDirectory(prefix="classifier-parity-test-") as temp_name:
            root = Path(temp_name)
            old_dir = root / "processor"
            old_dir.mkdir()
            old_path = old_dir / "classifier.py"
            shim = "from classifier import classify\n"
            new_dir = root / "new" / "classifier"
            new_dir.mkdir(parents=True)
            new_path = new_dir / "__init__.py"
            old_path.write_text(shim, encoding="utf-8")
            new_path.write_text(new_source, encoding="utf-8")

            def fake_git(_repo: Path, args: list[str]) -> str:
                if args[0] == "log":
                    return "split\npre-split\n"
                ref = args[-1]
                return shim if ref.startswith("split:") else old_source

            with patch.object(harness, "_run_git", side_effect=fake_git):
                result = harness.compare(
                    old_path,
                    new_path,
                    repo_root=root,
                    samples=10_000,
                    seed=9,
                    timeout_seconds=30,
                )

        self.assertEqual(result.samples, 10_000)
        self.assertEqual(result.seed, 9)
        self.assertEqual(result.old_origin, "Git pre-split:processor/classifier.py")

    def test_tuple_drift_is_reported(self) -> None:
        old_source = """
def classify(payload, kb_results=None):
    return {"priority": "normal", "sensitive": False, "should_notify_owner": False}
"""
        new_source = """
def classify(payload, kb_results=None):
    return {"priority": "high", "sensitive": True, "should_notify_owner": True}
"""
        with tempfile.TemporaryDirectory(prefix="classifier-mismatch-test-") as temp_name:
            root = Path(temp_name)
            old_path = root / "old.py"
            new_path = root / "new.py"
            old_path.write_text(old_source, encoding="utf-8")
            new_path.write_text(new_source, encoding="utf-8")
            with self.assertRaises(harness.ParityMismatch) as caught:
                harness.compare(
                    old_path,
                    new_path,
                    repo_root=root,
                    samples=5,
                    seed=1,
                    timeout_seconds=30,
                )
        self.assertIn('"index": 0', str(caught.exception))
        self.assertIn('"old": ["normal", false, false]', str(caught.exception))
        self.assertIn('"new": ["high", true, true]', str(caught.exception))

    def test_worker_rejects_network_attempts(self) -> None:
        network_source = """
import socket

def classify(payload, kb_results=None):
    socket.create_connection(("127.0.0.1", 9), timeout=0.1)
    return {"priority": "normal", "sensitive": False, "should_notify_owner": False}
"""
        with tempfile.TemporaryDirectory(prefix="classifier-network-test-") as temp_name:
            root = Path(temp_name)
            old_path = root / "old.py"
            new_path = root / "new.py"
            old_path.write_text(network_source, encoding="utf-8")
            new_path.write_text(network_source, encoding="utf-8")
            with self.assertRaises(harness.ParityError) as caught:
                harness.compare(
                    old_path,
                    new_path,
                    repo_root=root,
                    samples=1,
                    seed=1,
                    timeout_seconds=30,
                )
        self.assertIn("parity worker blocked socket.", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
