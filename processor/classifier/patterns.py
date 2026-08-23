"""Compiled patterns that coordinate the classifier's rule families."""

from __future__ import annotations

import re


_TRADE_ENQUIRY_RE = re.compile(
    r"\b(wholesale|stockist|stock\s+your|stocking\s+your|trade\s+(?:account|"
    r"price|pricing|enquiry|inquiry)|reseller|retail\s+account|bulk\s+order|"
    r"collab|collaboration|brand\s+partnership|press\s+(?:sample|enquiry|"
    r"inquiry|pack)|pr\s+(?:sample|enquiry|inquiry)|influencer|"
    r"gifting\s+opportunity|media\s+pack)\b",
    re.IGNORECASE,
)
_ESCALATE_RE = re.compile(r"\bescalate\s+(?:this|my)\b", re.IGNORECASE)
_ESCALATE_NEGATED_RE = re.compile(
    r"\b(?:do\s?n'?t|do\s+not|no\s+need\s+to|not?\s+need|rather\s+not|"
    r"please\s+do\s?n'?t)\s+(?:\w+\s+){0,2}escalate\b",
    re.IGNORECASE,
)
_FOLLOWUP_PATTERN = re.compile(
    r"(following\s+up|follow\s?up|still\s+(no|waiting)|yet\s+again|"
    r"any\s+(update|response|reply|answer)|"
    r"(2nd|3rd|second|third|fourth)\s+(time|attempt|message|email|follow))",
    re.IGNORECASE,
)
_MAIN_HIGH_SENSITIVE_PATTERN = re.compile(
    r"\b(final\s+sale|change\s+(?:my\s+)?(?:shipping\s+)?address|"
    r"wrong\s+address|update\s+(?:my\s+)?address|new\s+address|"
    r"cancel(?:lation)?(?:\s+(?:my\s+)?(?:order|item|purchase))?)\b",
    re.IGNORECASE,
)
_HIGH_SENSITIVE_PATTERN = re.compile(
    r"\b(final\s+sale|change\s+(?:my\s+)?(?:shipping\s+)?address|"
    r"wrong\s+address|update\s+(?:my\s+)?address|new\s+address|"
    r"cancel(?:lation)?(?:\s+(?:my\s+)?(?:order|item|purchase))?|"
    r"(?:has\s?n'?t|has\s+not|have\s+not|have\s?n'?t)\s+"
    r"(?:arrived|turned\s+up|shown\s+up)|"
    r"still\s+(?:has\s?n'?t|have\s?n'?t|not)\s+(?:arrived|come|received)|"
    r"nothing\s+(?:has\s+|had\s+)?(?:arrived|come|turned\s+up|"
    r"showed\s+up|been\s+delivered)|not\s+(?:been\s+)?delivered)\b",
    re.IGNORECASE,
)


__all__ = [
    "_TRADE_ENQUIRY_RE", "_ESCALATE_RE", "_ESCALATE_NEGATED_RE",
    "_FOLLOWUP_PATTERN", "_MAIN_HIGH_SENSITIVE_PATTERN",
    "_HIGH_SENSITIVE_PATTERN",
]
