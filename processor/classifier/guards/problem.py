"""Shapes that turn a weak vocabulary match into a delivery problem."""

from __future__ import annotations

import re


_PROBLEM_CONTEXT_RE = re.compile(
    r"\b((?:arrived|came|turned\s+up|delivered|showed\s+up)\s+"
    r"(?:(?:completely|totally|badly|slightly|already|all|absolutely)\s+)?"
    r"(?:ripped|stained|torn|damaged|open|soaked|filthy|dirty)|"
    r"(?:a|an|the|one|another)\s+(?:ripped|stained|torn|damaged)\s+\w|"
    r"(?:tracking|courier|carrier|parcel|package)\s+"
    r"(?:has\s?n'?t|have\s?n'?t|has\s+not|is\s+stuck|stopped|shows\s+nothing|"
    r"says\s+nothing|never|is\s+lost|went\s+missing|has\s+vanished)|"
    r"no\s+tracking|tracking\s+number\s+does\s?n'?t|"
    r"still\s+waiting|still\s+not|no\s+update|"
    r"has\s?n'?t\s+moved|has\s+not\s+moved|"
    r"where\s+is|where\s+are|chasing|chase\s+this|follow(?:ing)?\s?up|"
    r"never\s+(?:came|arrived|turned\s+up)|why\b|"
    r"still\s+(?:has\s?n'?t|have\s?n'?t|no|nothing)|"
    r"(?:waiting|waited)\s+(?:for\s+)?(?:over\s+)?(?:(?:\d+|a|two|three)\s*)?"
    r"(?:days?|weeks?|months?)|"
    r"been\s+(?:over\s+)?(?:\d+|two|three|four)\s*(?:days?|weeks?|months?))",
    re.IGNORECASE,
)


__all__ = ["_PROBLEM_CONTEXT_RE"]
