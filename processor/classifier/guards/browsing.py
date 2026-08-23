"""Patterns identifying product, care, and pre-sale questions."""

from __future__ import annotations

import re


_BROWSING_QUESTION_RE = re.compile(
    r"\b(can\s+i|could\s+i|do\s+you|does\s+the|does\s+it|is\s+there|are\s+there|"
    r"am\s+i|how\s+do\s+i|how\s+can\s+i|how\s+to|how\s+would\s+i|"
    r"what'?s?\s+the\s+best\s+way|any\s+tips|is\s+it\s+possible|would\s+it\s+be|"
    r"can\s+you|could\s+you|would\s+you|will\s+you|do\s+i\s+need|"
    r"where\s+do\s+i|what\s+do\s+i|which\s+(?:size|one|colour|color)|"
    r"is\s+(?:the|this|that|it)\b|are\s+(?:the|these|those|they)\b|"
    r"was\s+(?:the|this|that|it)\b|were\s+(?:the|these|those|they)\b|"
    r"did\s+(?:the|this|that|it|you|they)\b)",
    re.IGNORECASE,
)


__all__ = ["_BROWSING_QUESTION_RE"]
