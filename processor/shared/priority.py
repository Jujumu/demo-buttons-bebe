"""Canonical priority lattice used by the processor.

The deterministic classifier still exposes its historical ``immediate``
label.  The Hermes and queue-facing contract uses the four-level lattice
below; the orchestrator maps the former to ``critical`` at that boundary.
Keeping the comparison here prevents individual components from quietly
inventing different escalation rules.
"""

from __future__ import annotations

from enum import Enum
from typing import TypeAlias


class Priority(str, Enum):
    """The persisted/Hermes priority levels, from least to most severe."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


RANK = {priority.value: rank for rank, priority in enumerate(Priority)}
PriorityValue: TypeAlias = str | Priority


def _value(priority: PriorityValue) -> str:
    """Return the normalized string form used by the public helpers."""

    if isinstance(priority, Priority):
        return priority.value
    return str(priority).strip().lower()


def normalize(
    priority: PriorityValue,
    *,
    default: PriorityValue = Priority.HIGH,
) -> str:
    """Return a canonical priority, replacing invalid values with *default*.

    The default is deliberately HIGH: malformed model output must remain a
    reviewable, elevated result rather than leaking an unknown value into the
    webhook API or being treated as LOW.
    """

    value = _value(priority)
    if value in RANK:
        return value
    fallback = _value(default)
    if fallback not in RANK:
        raise ValueError(f"invalid fallback priority: {fallback!r}")
    return fallback


def escalate(current: PriorityValue, candidate: PriorityValue) -> str:
    """Return the more severe of two priorities.

    A single unknown value yields the known value. If both are unknown, the
    result is CRITICAL so this helper never emits an invalid persisted value.
    """

    current_value = _value(current)
    candidate_value = _value(candidate)
    current_known = current_value in RANK
    candidate_known = candidate_value in RANK
    if not current_known and not candidate_known:
        return Priority.CRITICAL.value
    if not current_known:
        return candidate_value
    if not candidate_known:
        return current_value
    return candidate_value if RANK[candidate_value] > RANK[current_value] else current_value


def at_least(priority: PriorityValue, floor: PriorityValue) -> bool:
    """Whether *priority* meets or exceeds *floor* in the lattice."""

    value = _value(priority)
    floor_value = _value(floor)
    if value not in RANK or floor_value not in RANK:
        return False
    return RANK[value] >= RANK[floor_value]
