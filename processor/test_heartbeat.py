"""Offline tests for processor/heartbeat.sh.

The script only ever shells out to systemctl / journalctl / curl, so we can
exercise every branch by putting stubs for those three on PATH and reading
back what the script tried to do. Nothing here touches systemd, the network,
or the live processor.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent / "heartbeat.sh"

_SYSTEMCTL_STUB = """#!/bin/sh
# usage: systemctl is-active <unit>
if [ "$1" = "is-active" ]; then
    printf '%s\\n' "${FAKE_ACTIVE:-active}"
    [ "${FAKE_ACTIVE:-active}" = "active" ] && exit 0 || exit 3
fi
exit 0
"""

_JOURNALCTL_STUB = """#!/bin/sh
# Emit FAKE_JOURNAL_LINES lines of pretend journal output.
i=0
while [ "$i" -lt "${FAKE_JOURNAL_LINES:-3}" ]; do
    echo "pretend log line $i"
    i=$((i + 1))
done
exit 0
"""

_CURL_STUB = """#!/bin/sh
# Record every argument, one per line, then succeed.
for arg in "$@"; do
    printf '%s\\n' "$arg" >> "$CURL_LOG"
done
printf -- '--END--\\n' >> "$CURL_LOG"
exit 0
"""


class HeartbeatTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.bin = self.tmp / "bin"
        self.bin.mkdir()
        for name, body in (
            ("systemctl", _SYSTEMCTL_STUB),
            ("journalctl", _JOURNALCTL_STUB),
            ("curl", _CURL_STUB),
        ):
            path = self.bin / name
            path.write_text(body, encoding="utf-8")
            path.chmod(0o755)
        self.state_file = self.tmp / "state" / "heartbeat.state"
        self.curl_log = self.tmp / "curl.log"
        self.addCleanup(self._tmp.cleanup)

    def run_heartbeat(self, *, active: str = "active", journal_lines: int = 3,
                      url: str = "http://127.0.0.1:8085/send",
                      secret: str = "s3cret") -> subprocess.CompletedProcess:
        env = dict(os.environ)
        env["PATH"] = f"{self.bin}:{env.get('PATH', '')}"
        env["FAKE_ACTIVE"] = active
        env["FAKE_JOURNAL_LINES"] = str(journal_lines)
        env["CURL_LOG"] = str(self.curl_log)
        env["HEARTBEAT_STATE_FILE"] = str(self.state_file)
        env["PROCESSOR_UNIT"] = "buttonsbebe-processor"
        env["PROCESSOR_STALE_MINUTES"] = "10"
        env["WHATSAPP_SEND_URL"] = url
        env["WA_SEND_SECRET"] = secret
        return subprocess.run(
            ["bash", str(SCRIPT)], env=env, capture_output=True, text=True, timeout=60,
        )

    def sent(self) -> str:
        return self.curl_log.read_text(encoding="utf-8") if self.curl_log.exists() else ""

    def alert_count(self) -> int:
        return self.sent().count("--END--")

    # ── happy path ──────────────────────────────────────────────────────
    def test_healthy_processor_sends_nothing(self):
        proc = self.run_heartbeat()
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(self.alert_count(), 0)
        self.assertFalse(self.state_file.exists())
        self.assertIn("processor healthy", proc.stderr)

    # ── outage detection ────────────────────────────────────────────────
    def test_inactive_service_alerts_once_and_latches(self):
        first = self.run_heartbeat(active="failed")
        self.assertEqual(first.returncode, 0)
        self.assertEqual(self.alert_count(), 1)
        self.assertIn("looks DOWN", self.sent())
        self.assertTrue(self.state_file.exists())

        second = self.run_heartbeat(active="failed")
        self.assertEqual(second.returncode, 0)
        self.assertEqual(self.alert_count(), 1, "must not re-alert while still down")
        self.assertIn("staying quiet", second.stderr)

    def test_recovery_clears_state_and_sends_one_all_clear(self):
        self.run_heartbeat(active="inactive")
        self.assertEqual(self.alert_count(), 1)

        recovered = self.run_heartbeat(active="active")
        self.assertEqual(recovered.returncode, 0)
        self.assertEqual(self.alert_count(), 2)
        self.assertIn("back up", self.sent())
        self.assertFalse(self.state_file.exists())

        quiet = self.run_heartbeat(active="active")
        self.assertEqual(quiet.returncode, 0)
        self.assertEqual(self.alert_count(), 2, "must not repeat the all-clear")

    def test_active_but_silent_journal_is_treated_as_hung(self):
        proc = self.run_heartbeat(active="active", journal_lines=0)
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(self.alert_count(), 1)
        self.assertIn("possibly hung", self.sent())

    # ── auth contract (must match whatsapp_notifier.py) ─────────────────
    def test_secret_travels_in_the_header_never_in_the_url(self):
        self.run_heartbeat(active="failed", url="http://127.0.0.1:8085/send",
                           secret="topsecret")
        sent = self.sent()
        self.assertIn("Authorization: Bearer topsecret", sent)
        url_lines = [ln for ln in sent.splitlines() if ln.startswith("http")]
        self.assertTrue(url_lines)
        for line in url_lines:
            self.assertNotIn("topsecret", line)

    def test_body_is_valid_json(self):
        import json
        self.run_heartbeat(active="failed")
        lines = self.sent().splitlines()
        body = lines[lines.index("-d") + 1]
        self.assertIn("text", json.loads(body))

    # ── fail-soft behaviour ─────────────────────────────────────────────
    def test_missing_credentials_logs_but_never_fails(self):
        proc = self.run_heartbeat(active="failed", url="", secret="")
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(self.alert_count(), 0)
        self.assertIn("WHATSAPP_SEND_URL", proc.stderr)
        self.assertTrue(self.state_file.exists(),
                        "still latch, so we do not spam once creds come back")

    def test_missing_systemctl_exits_zero(self):
        """A non-systemd host must be a no-op, not an error."""
        import shutil

        # Build a PATH that deliberately contains no systemctl at all, while
        # still offering the handful of coreutils the script touches before
        # the systemctl check.
        sandbox = self.tmp / "nosystemd"
        sandbox.mkdir()
        for tool in ("date", "dirname", "mkdir", "rm"):
            real = shutil.which(tool)
            if real:
                (sandbox / tool).symlink_to(real)
        (self.bin / "systemctl").unlink()

        env = dict(os.environ)
        env["PATH"] = f"{self.bin}:{sandbox}"
        env["HEARTBEAT_STATE_FILE"] = str(self.state_file)
        env["CURL_LOG"] = str(self.curl_log)
        bash = shutil.which("bash") or "/bin/bash"
        proc = subprocess.run([bash, str(SCRIPT)], env=env,
                              capture_output=True, text=True, timeout=60)
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(self.alert_count(), 0)
        self.assertIn("systemctl not available", proc.stderr)


if __name__ == "__main__":
    unittest.main()
