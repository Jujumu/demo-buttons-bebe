"""Tests for the Hermes tool allow-list (DEV-ISSUES #8).

The processor used to launch `hermes --yolo -z "..."`. --yolo skips approval
for EVERY tool call, and ~/.hermes/config.yaml grants the CLI platform the
`terminal` and `file` toolsets - so the only thing stopping a prompt-injected
ticket from running a shell command was convention.

These tests pin the replacement: an explicit toolset allow-list, no --yolo, and
an escape hatch that has to be switched on deliberately.

Nothing here executes Hermes. build_hermes_command() is a pure function.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

PROCESSOR_DIR = Path(__file__).resolve().parent
WEBHOOK_SRC = PROCESSOR_DIR.parent / "webhook" / "src"
sys.path[:0] = [str(PROCESSOR_DIR), str(WEBHOOK_SRC)]

from config import ProcessorSettings  # noqa: E402
from hermes_runner import build_hermes_command, process_ticket_with_hermes  # noqa: E402
from hermes_runner import runner  # noqa: E402

DEFAULT_TOOLSETS = "mcp-buttonsbebe_kb,mcp-buttonsbebe_redo,mcp-buttonsbebe_gorgias"
TOKEN = "0123456789abcdef"


def tagged_output() -> str:
    return (
        f"<DRAFT:{TOKEN}>Hi! Your order ships in 24-48 hours.</DRAFT:{TOKEN}>\n"
        f"JSON_RESULT[{TOKEN}]: "
        + json.dumps(
            {
                "priority": "normal",
                "reason": "ok",
                "action": "drafted",
                "notify_owner": False,
                "gorgias_priority_set": False,
                "note_posted": False,
            },
            separators=(",", ":"),
        )
    )


def _settings(**overrides):
    base = {"hermes_toolsets": DEFAULT_TOOLSETS, "hermes_skip_approval": False,
            "job_timeout": 30}
    base.update(overrides)
    return SimpleNamespace(**base)


class CommandShapeTests(unittest.TestCase):
    def test_default_command_has_no_yolo(self):
        cmd = build_hermes_command("hello", _settings())
        self.assertNotIn("--yolo", cmd)

    def test_default_command_passes_the_three_read_only_toolsets(self):
        cmd = build_hermes_command("hello", _settings())
        self.assertEqual(cmd[0], "hermes")
        self.assertIn("-t", cmd)
        self.assertEqual(cmd[cmd.index("-t") + 1], DEFAULT_TOOLSETS)
        self.assertEqual(cmd[-2:], ["-z", "hello"])

    def test_shell_and_file_toolsets_are_never_requested(self):
        joined = " ".join(build_hermes_command("hello", _settings()))
        for dangerous in ("terminal", "file", "code_execution", "browser",
                          "computer_use", "shell"):
            self.assertNotIn(dangerous, joined)

    def test_toolset_list_is_normalised(self):
        cmd = build_hermes_command(
            "hi", _settings(hermes_toolsets=" mcp-a , mcp-b ,, mcp-a "))
        self.assertEqual(cmd[cmd.index("-t") + 1], "mcp-a,mcp-b")

    def test_empty_toolset_list_omits_the_flag_entirely(self):
        # "" means "whatever config.yaml grants" — allowed, but it must not
        # produce a bare `-t` that Hermes would choke on.
        cmd = build_hermes_command("hi", _settings(hermes_toolsets=""))
        self.assertNotIn("-t", cmd)
        self.assertEqual(cmd, ["hermes", "-z", "hi"])

    def test_prompt_is_always_the_final_argument(self):
        for toolsets in (DEFAULT_TOOLSETS, ""):
            for skip in (True, False):
                with self.subTest(toolsets=bool(toolsets), skip=skip):
                    cmd = build_hermes_command(
                        "the prompt",
                        _settings(hermes_toolsets=toolsets, hermes_skip_approval=skip))
                    self.assertEqual(cmd[-1], "the prompt")
                    self.assertEqual(cmd[-2], "-z")


class EscapeHatchTests(unittest.TestCase):
    def test_yolo_only_appears_when_explicitly_enabled(self):
        cmd = build_hermes_command("hi", _settings(hermes_skip_approval=True))
        self.assertIn("--yolo", cmd)
        # even then, the allow-list still applies
        self.assertEqual(cmd[cmd.index("-t") + 1], DEFAULT_TOOLSETS)

    def test_enabling_the_escape_hatch_is_logged_as_a_warning(self):
        with patch.object(runner, "log_event") as log_event:
            build_hermes_command("hi", _settings(hermes_skip_approval=True))
        self.assertTrue(log_event.called)
        level = log_event.call_args[0][1]
        self.assertEqual(level, "WARNING")


class DefaultsTests(unittest.TestCase):
    def test_shipped_defaults_are_the_locked_down_ones(self):
        # Read the real Settings defaults, not the test doubles above, so a
        # careless edit to config.py fails here.
        settings = ProcessorSettings()
        self.assertEqual(settings.hermes_toolsets, DEFAULT_TOOLSETS)
        self.assertFalse(settings.hermes_skip_approval)


class RunnerIntegrationTests(unittest.TestCase):
    def test_the_runner_actually_uses_the_allow_list(self):
        with patch.object(
            runner, "get_settings", return_value=_settings()
        ), patch.object(
            runner, "_make_run_token", return_value=TOKEN
        ), patch.object(
            runner.subprocess,
            "run",
            return_value=SimpleNamespace(
                returncode=0, stderr="", stdout=tagged_output()
            ),
        ) as run:
            process_ticket_with_hermes(
                ticket_id=1,
                message_text="Where is my order?",
                ticket_subject="WISMO",
                customer_email="c@example.com",
                intents=[],
            )
        cmd = run.call_args[0][0]
        self.assertEqual(cmd[0], "hermes")
        self.assertNotIn("--yolo", cmd)
        self.assertEqual(cmd[cmd.index("-t") + 1], DEFAULT_TOOLSETS)


if __name__ == "__main__":
    unittest.main()
