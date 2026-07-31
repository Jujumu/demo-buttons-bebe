"""The processing loop must stay responsive while a job is working.

WHY THIS FILE EXISTS

Three rounds of review found five catastrophic-backtracking patterns between
the classifier and the draft cleaner - one stalling a single ticket for 204
seconds. Each was fixed, and a measurement-based guard now watches for the
next one.

But the reason each of those was a BLOCKER rather than "a slow ticket" was
structural, not textual: `deterministic_classify` and `process_ticket_with_hermes`
are synchronous and CPU-bound, and they were called directly inside the job
coroutine. `asyncio.wait_for` cannot interrupt a blocked synchronous call, so
while a pattern spun:

  * the event loop was frozen,
  * `settings.job_timeout` never fired,
  * the idle heartbeat line at the bottom of run_processor() was never
    emitted - and heartbeat.sh reads exactly that line to decide the loop is
    wedged, so the watchdog stayed quiet too,
  * the exclusive flock stayed held, so no other processor could take over.

One email stopped the shop, silently.

Both calls now go through asyncio.to_thread. That cannot kill a spinning
thread - the patterns still have to be linear - but it means the timeout
fires, the alert is raised, and the heartbeat keeps beating, so the next one
is visible in minutes instead of never.
"""

from __future__ import annotations

import asyncio
import inspect
import re
import sys
import time
import unittest
from pathlib import Path

PROCESSOR_DIR = Path(__file__).resolve().parent
WEBHOOK_SRC = PROCESSOR_DIR.parent / "webhook" / "src"
sys.path[:0] = [str(PROCESSOR_DIR), str(WEBHOOK_SRC)]


class TimeoutCanInterruptTests(unittest.TestCase):
    """The property itself, demonstrated rather than asserted about."""

    SPIN = 3.0
    TIMEOUT = 0.5

    @staticmethod
    def _spin(seconds: float) -> str:
        started = time.perf_counter()
        while time.perf_counter() - started < seconds:
            pass
        return "finished"

    def test_a_direct_synchronous_call_defeats_the_timeout(self):
        # This is what the code used to do. Kept as the control: if this ever
        # starts raising TimeoutError, the test below proves nothing.
        async def job():
            return self._spin(self.SPIN)

        async def main():
            return await asyncio.wait_for(job(), timeout=self.TIMEOUT)

        started = time.perf_counter()
        self.assertEqual(asyncio.run(main()), "finished")
        self.assertGreater(time.perf_counter() - started, self.SPIN * 0.8,
                           "the control did not actually block")

    def test_to_thread_lets_the_timeout_fire(self):
        async def job():
            return await asyncio.to_thread(self._spin, self.SPIN)

        async def main():
            # Timed INSIDE the loop. asyncio.run() shuts the default executor
            # down with wait=True, so measuring around it would just time the
            # spinning thread draining - which is exactly what to_thread
            # cannot prevent, and not what this test is about. What matters is
            # that control came back to the loop while the thread was still
            # going.
            started = time.perf_counter()
            try:
                await asyncio.wait_for(job(), timeout=self.TIMEOUT)
            except asyncio.TimeoutError:
                return time.perf_counter() - started
            return None

        elapsed = asyncio.run(main())
        self.assertIsNotNone(elapsed, "the timeout never fired")
        self.assertLess(elapsed, self.SPIN * 0.8,
                        "the timeout did not fire promptly")


class BlockingCallsAreOffTheLoopTests(unittest.TestCase):
    """...and the orchestrator actually uses it, for both blocking calls.

    Structural, because the behavioural version would need a real 200-second
    regex to demonstrate anything - and the whole point is that no such regex
    should exist any more.
    """

    @staticmethod
    def _source() -> str:
        import orchestrator

        return inspect.getsource(orchestrator.process_customer_message)

    def test_the_classifier_runs_off_the_event_loop(self):
        source = self._source()
        self.assertRegex(
            source,
            r"await\s+asyncio\.to_thread\(\s*deterministic_classify",
            "deterministic_classify is CPU-bound and synchronous; called "
            "directly it freezes the loop and the job timeout cannot fire")

    def test_hermes_runs_off_the_event_loop(self):
        source = self._source()
        self.assertRegex(
            source,
            r"await\s+asyncio\.to_thread\(\s*\n?\s*process_ticket_with_hermes",
            "process_ticket_with_hermes blocks on subprocess.run for the "
            "whole Hermes call as well as its own parsing")

    def test_neither_is_still_called_directly(self):
        source = self._source()
        for name in ("deterministic_classify", "process_ticket_with_hermes"):
            with self.subTest(name=name):
                direct = re.search(rf"(?<!to_thread\(\s)\b{name}\(", source)
                if direct:
                    context = source[max(0, direct.start() - 60):direct.end()]
                    self.assertIn("to_thread", context,
                                  f"{name} is called directly at: ...{context}")


if __name__ == "__main__":
    unittest.main()
