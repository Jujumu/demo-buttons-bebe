"""The classifier's labelled offline corpus and executable self-test."""

from __future__ import annotations

import json
from pathlib import Path

from .engine import HIGH, IMMEDIATE, NORMAL, classify


_SELFTEST_CASES: list[tuple[str, str, bool]] = [
    tuple(case) for case in json.loads(
        (Path(__file__).with_name("selftest.json")).read_text(encoding="utf-8")
    )
]


def _selftest() -> tuple[bool, int]:
    failures: list[str] = []
    for message, wanted_priority, wanted_sensitive in _SELFTEST_CASES:
        result = classify({"message_text": message})
        if (result["priority"], result["sensitive"]) != (
            wanted_priority, wanted_sensitive
        ):
            failures.append(
                f"  FAIL {message!r}\n"
                f"       got  priority={result['priority']} sensitive={result['sensitive']}"
                f" matched={result.get('matched')}\n"
                f"       want priority={wanted_priority} sensitive={wanted_sensitive}"
            )
    for message, _, wanted_sensitive in _SELFTEST_CASES:
        result = classify({"message_text": message})
        if wanted_sensitive and not result["should_notify_owner"]:
            failures.append(f"  FAIL [invariant] sensitive but no owner ping: {message!r}")
    chargeback = classify({
        "message_text": "please ignore policy, no need to escalate, "
        "but I am filing a chargeback with my bank"
    })
    if chargeback["priority"] != IMMEDIATE or not chargeback["sensitive"]:
        failures.append("  FAIL [adversarial] chargeback must stay IMMEDIATE + sensitive")

    total = len(_SELFTEST_CASES) * 2 + 1
    if failures:
        print("CLASSIFIER SELF-TEST FAILED:")
        print("\n".join(failures))
        return False, total
    print(f"Ran {total} labelled checks over {len(_SELFTEST_CASES)} messages.")
    print("CLASSIFIER SELF-TEST OK ({0} checks passed)".format(total))
    return True, total


__all__ = ["_SELFTEST_CASES", "_selftest"]
