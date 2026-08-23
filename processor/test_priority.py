from __future__ import annotations

import unittest
from pathlib import Path
import sys

# The production modules are also runnable as flat scripts from processor/;
# mirror that import shape when the release gate discovers this test as
# processor.test_priority from the repository root.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from shared.priority import Priority, RANK, at_least, escalate, normalize


class PriorityTests(unittest.TestCase):
    def test_escalate_promotes_normal_to_high(self) -> None:
        self.assertEqual(escalate(Priority.NORMAL, Priority.HIGH), "high")

    def test_escalate_never_deescalates_critical(self) -> None:
        self.assertEqual(escalate("critical", "normal"), "critical")

    def test_at_least_uses_the_shared_lattice(self) -> None:
        self.assertTrue(at_least("critical", Priority.HIGH))
        self.assertTrue(at_least(" CRITICAL ", Priority.HIGH))
        self.assertTrue(at_least("high", "high"))
        self.assertFalse(at_least("normal", "high"))
        self.assertFalse(at_least("bogus", "bogus"))

    def test_unknown_current_value_can_still_be_escalated(self) -> None:
        self.assertEqual(escalate("unknown", "high"), "high")
        self.assertEqual(escalate("normal", "unknown"), "normal")
        self.assertEqual(escalate("unknown", "bogus"), "critical")
        self.assertEqual(RANK, {"low": 0, "normal": 1, "high": 2, "critical": 3})

    def test_normalize_canonicalizes_and_fails_closed(self) -> None:
        self.assertEqual(normalize(" CRITICAL "), "critical")
        self.assertEqual(normalize("bogus"), "high")
        with self.assertRaises(ValueError):
            normalize("bogus", default="also-bogus")


if __name__ == "__main__":
    unittest.main()
