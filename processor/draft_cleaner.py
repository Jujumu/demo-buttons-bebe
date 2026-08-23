"""Last-mile AI-draft cleaning and customer acknowledgement gating.

This standard-library-only module can shorten or suppress a draft, never send
or lengthen one. See ADR-015 §2.4 for the safety and bounded-work rationale.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# ADR-015 §2.4 — anchored self-talk may only shorten or suppress; tails stay visible.
_SELF_TALK_MARKERS = [
    # "The response above was complete..."  (QA #01/#04/#10)
    r"the response above was complete",
    r"the (?:previous|prior) (?:response|reply|draft) (?:was|is) (?:already )?complete",
    # "The above response addresses the question."
    r"the above (?:response|reply|draft) ",
    # "This reply is complete." / "This response above is complete."
    r"this (?:response|reply|draft) (?:above )?(?:is|was) (?:now )?complete",
    # "I have completed the response." / "I have now finished this draft."
    r"i have (?:now )?(?:completed|finished) (?:the|this|my) (?:response|reply|draft)",
    # Internal notes leave the sendable body but are returned to the reviewer.
    r"notes? (?:to|for) (?:the )?(?:reviewer|agent|human)\b",
    r"^internal\b[:\s]",
    r"for internal use\b",
    r"confidence:\s",
    # ADR-015 §2.4 — the shared prefix handles dashes; overlapping classes do not.
    r"\[?end of (?:the\s+)?(?:response|reply|draft)\]?",
    # Completion variants observed in model output.
    r"(?:the\s+)?(?:response|reply|draft)\s+above\s+(?:is|was)\s+"
    r"(?:already\s+|now\s+)?complete",
    # "Draft complete." / "[Draft complete]"
    r"\[?(?:draft|response|reply)\s+complete\b",
    # "I've completed the draft." / "I have written the response above."
    r"i(?:'ve| have)\s+(?:completed|written|finished)\s+(?:the|this|my)\s+"
    r"(?:response|reply|draft)",
    # An internal agent note is not customer-facing text.
    r"agent[\s-]note\b",
    r"\(internal[:\s]",
    # "As an AI, I cannot ..." style refusals leaking into a draft.
    r"as an ai\b.*\bi (?:cannot|can't|am unable)",
]
_MARKER_RE = re.compile(
    r"^[\s>*#\-]*(?:" + "|".join(_SELF_TALK_MARKERS) + r")",
    re.IGNORECASE,
)

# Hard bounds on what should_draft() will scan. See the note in that function:
# these are a second line of defence behind the patterns themselves, because
# this gate runs synchronously on a single-process pipeline.
_MAX_GATE_SUBJECT = 2_000
_MAX_GATE_MESSAGE = 20_000

# A repeated block must be at least this many normalised characters before we
# treat it as a genuine duplication. Keeps short, legitimately-repeated content
# (e.g. "Yes.\n\nYes.") from being collapsed.
_MIN_DUP_CHARS = 40


@dataclass
class CleanResult:
    text: str
    no_draft: bool = False
    reasons: list[str] = field(default_factory=list)
    # The cut tail, returned without semantic filtering so warnings reach review.
    removed_note: str = ""


@dataclass
class ShouldDraft:
    ok: bool
    reason: str = ""


def _cut_self_talk(text: str) -> tuple[str, str]:
    """Cut from the first self-talk line and return body plus removed tail.

    ADR-015 §2.4 explains why the tail is surfaced instead of keyword-filtered.
    """
    lines = text.splitlines()
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not _MARKER_RE.match(stripped):
            continue
        return "\n".join(lines[:i]).rstrip(), "\n".join(lines[i:]).strip()
    return text, ""


def _normalise(block: str) -> str:
    """Whitespace-flatten + lowercase, so two copies that differ only in spacing
    or newlines compare equal."""
    return re.sub(r"\s+", " ", block).strip().lower()


def _repeated_unit(norm: str, k: int) -> str | None:
    """If `norm` (already whitespace-normalised) is exactly ``k`` copies of a base
    string — optionally single-space-joined, because normalisation turns any
    separator (blank line, newline, spaces) between the copies into one space —
    return that base string; otherwise None.

    Only meaningful (>= _MIN_DUP_CHARS) bases count, so we never collapse a tiny
    accidental repeat.
    """
    n = len(norm)
    # Prefer the "joined by one space" reading (the usual case), then the
    # "no separator at all" reading.
    for sep in (1, 0):
        if (n - sep * (k - 1)) % k != 0:
            continue
        unit_len = (n - sep * (k - 1)) // k
        if unit_len < _MIN_DUP_CHARS:
            continue
        base = norm[:unit_len]
        if norm == (" " * sep).join([base] * k):
            return base
    return None


def _raw_prefix_for_norm(raw: str, base: str) -> str | None:
    """Return the shortest prefix of `raw` whose normalisation equals `base`.

    We rebuild the normalised form one character at a time and stop at the exact
    raw offset where the first copy ends. That keeps the first copy in its
    ORIGINAL formatting (capitalisation, line breaks) instead of the flattened
    lower-cased form.
    """
    out: list[str] = []
    prev_space = True  # leading whitespace is dropped by _normalise
    for idx, ch in enumerate(raw):
        if ch.isspace():
            if not prev_space:
                out.append(" ")
                prev_space = True
        else:
            out.append(ch.lower())
            prev_space = False
            # compare only once we could plausibly have reached `base`
            if len(out) >= len(base):
                cur = "".join(out).rstrip()
                if cur == base:
                    return raw[: idx + 1]
                if len(cur) > len(base):
                    return None
    return None


def _dedupe_repeats(text: str) -> tuple[str, bool]:
    """If the whole draft is the same content repeated at least twice, keep one.

    Works no matter how the copies are separated (blank line, single newline, or
    a single space) because it compares the whitespace-normalised whole text.
    Returns (possibly-shortened text, whether a duplicate was removed).
    """
    stripped = text.strip()
    norm = _normalise(stripped)
    if len(norm) < _MIN_DUP_CHARS:
        return stripped, False

    # ADR-015 §2.4 — test every bounded copy count, largest first.
    max_k = max(2, len(norm) // _MIN_DUP_CHARS)
    for k in range(max_k, 1, -1):
        base = _repeated_unit(norm, k)
        if base is None:
            continue
        raw_first = _raw_prefix_for_norm(stripped, base)
        if raw_first is not None:
            return raw_first.strip(), True
        # Fallback (should be rare): split on blank lines and keep the first
        # 1/k of the paragraphs when they divide evenly.
        paras = [p for p in re.split(r"\n\s*\n", stripped) if p.strip()]
        if paras and len(paras) % k == 0:
            keep = paras[: len(paras) // k]
            return "\n\n".join(keep).strip(), True

    return stripped, False


def clean_draft(text: str) -> CleanResult:
    """Clean an AI draft before it is shown to a human / posted anywhere."""
    if text is None or not str(text).strip():
        return CleanResult(text="", no_draft=True, reasons=["empty draft"])

    out = str(text)
    reasons: list[str] = []
    removed: list[str] = []

    # Four shortening-only passes reach a bounded fixed point.
    for _ in range(4):
        out, cut = _cut_self_talk(out)
        if cut:
            removed.append(cut)
            if "stripped model self-commentary" not in reasons:
                reasons.append("stripped model self-commentary")

        out, deduped = _dedupe_repeats(out)
        if deduped and "removed duplicated draft body" not in reasons:
            reasons.append("removed duplicated draft body")

        if not (cut or deduped):
            break

    out = out.strip()
    note = "\n".join(removed).strip()
    if not out:
        return CleanResult(
            text="", no_draft=True,
            reasons=reasons + ["nothing left after cleaning"],
            removed_note=note,
        )
    return CleanResult(text=out, no_draft=False, reasons=reasons,
                       removed_note=note)


# ADR-015 §2.4 — acknowledgement suppression is a bounded token allow-list.

# A genuine "this conversation is finished" signal. One of these must be
# present before anything is suppressed.
_ACK_ANCHORS = frozenset({
    "thanks", "thank", "thanx", "thx", "ty", "tysm", "cheers",
    "appreciate", "appreciated", "appreciation",
    "ok", "okay", "kk", "noted", "understood", "received", "got",
    "perfect", "great", "awesome", "excellent", "brilliant", "amazing",
})

# Deliberately short: any word that could carry a complaint or decision stays out.
_ACK_FILLER = frozenset({
    "a", "again", "all", "and", "at", "bye", "dear", "everyone", "folks",
    "for", "from", "guys", "hello", "hey", "hi", "in", "it", "its", "lot",
    "lots", "love", "loved", "lovely", "me", "much", "my", "night", "nice",
    "of", "oh", "on", "regards", "so", "super", "team", "that", "the",
    "this", "to", "too", "u", "very", "we", "weekend", "with", "you",
    "your", "yours", "x", "xx", "xxx",
})

# The subset that can stand alone as a whole message and mean nothing but
# "we are done here".
_GRATITUDE_ANCHORS = frozenset({
    "thanks", "thank", "thanx", "thx", "ty", "tysm", "cheers",
    "appreciated", "appreciation",
})

# Words that ANSWER a question rather than close a conversation. If the agent
# last asked "shall I cancel order #10234 before it ships?", every one of
# these is a yes - and suppressing the reply stores an empty console card with
# no action controls while the order ships.
_DECISION_ANCHORS = frozenset({
    "ok", "okay", "kk", "noted", "understood", "received", "got",
})

_ACK_ALLOWED = _ACK_ANCHORS | _ACK_FILLER

# Word characters, Unicode-aware. A Latin-only [0-9a-z]+ found NO tokens in
# Chinese, Cyrillic, Hebrew or Arabic, so "ok 我要退款" ("ok, I want a refund")
# looked like a bare "ok" and was suppressed.
_TOKEN_RE = re.compile(r"\w+", re.UNICODE)

# Emoji that mean "we are done here". A message made only of these is an ack.
# Anything NOT on this list — every angry or confused emoji — is content.
_SAFE_EMOJI = (
    "\U0001F44D", "\U0001F64F", "\u2764", "\U0001F60A", "\U0001F642",
    "\U0001F600", "\U0001F601", "\U0001F970", "\U0001F60D", "\U0001F44C",
    "\u2705", "\U0001F389", "\U0001F495", "\U0001F49B", "\U0001F44F",
    "\U0001F929", "\u2b50", "\U0001F31F", "\U0001F338", "\U0001F49C",
)

# Skin-tone modifiers, variation selectors and zero-width characters. Stripped
# before anything else: "\U0001F44D\U0001F3FD" (a thumbs-up with a skin tone) is
# still a thumbs-up, and a zero-width space is still an empty message.
_DECORATION = (
    "".join(chr(c) for c in range(0x1F3FB, 0x1F400))   # skin tones
    + "\ufe0e\ufe0f"                                   # variation selectors
    + "\u200b\u200c\u200d\ufeff"                       # zero-width
)

# Punctuation that carries no meaning on its own. "?" is deliberately absent —
# a question mark is always content, wherever it appears.
_INERT_PUNCT = " \t\r\n.,~-\u2013\u2014\u2026'\"()[]:;*_/\\"


def _strip_decoration(text: str) -> str:
    for ch in _DECORATION:
        if ch in text:
            text = text.replace(ch, "")
    for emoji in _SAFE_EMOJI:
        if emoji in text:
            text = text.replace(emoji, "")
    return _HAPPY_EMOTICON_RE.sub(" ", text)


# Sad ASCII emoticons are content; (?!/) keeps URL schemes out of the match.
_EMOTICON_RE = re.compile(r"[:;=8][-'~^]?(?:[(\[|\\<]|/(?!/))")

# ...and the happy ones are stripped like an emoji, so their mouth character
# does not survive as a stray token ("thank you :D" tokenised a bare "d").
_HAPPY_EMOTICON_RE = re.compile(r"[:;=8][-'~^]?[)\]>DdPpOo3*]+")


# ADR-015 §2.4 — subject noise uses one whitespace class to stay linear.
_SUBJECT_NOISE_RE = re.compile(
    r"^\s*((re|fw|fwd|aw|sv)\s*:\s*)+|"
    r"\border[\s#]*\d+|#\s*\d+|"
    r"\b(no\s+subject|message\s+from\s+(the\s+)?contact\s+form|"
    r"contact\s+form|order\s+confirmation|your\s+order|"
    r"buttons\s+bebe|customer\s+(service|support)|support\s+request|"
    r"new\s+message|website\s+enquiry|enquiry|update)\b|"
    r"\b(your|our|my|the|a|an|order|orders|ticket|case|ref|reference)\b",
    re.IGNORECASE,
)


def _carries_no_content(value: str | None) -> bool:
    """True when this ONE piece of text has nothing in it to answer.

    Evaluated per field. should_draft() calls it separately on the message and
    on the subject, and suppresses only when BOTH are empty — concatenating
    them was a token union, so an ack subject could supply the missing anchor
    and silently suppress a real question in the body.
    """
    if value is None:
        return True
    text = _strip_decoration(str(value))
    if not text.strip():
        return True

    # A question mark is content, full stop. The token scan drops punctuation,
    # so "Have you received it?" used to read as bare filler plus the anchor
    # "received" and was suppressed.
    if "?" in text:
        return False

    # A sad or frustrated face is content, exactly like an angry emoji.
    if _EMOTICON_RE.search(text):
        return False

    tokens = _TOKEN_RE.findall(text.lower())

    # Anything left after removing words and inert punctuation is a symbol the
    # customer chose deliberately — an angry emoji, a currency sign. "!" only
    # counts as inert when there are words around it, so a bare "!" is content.
    residue = _TOKEN_RE.sub(" ", text)
    inert = _INERT_PUNCT + ("!" if tokens else "")
    if any(ch not in inert and not ch.isspace() for ch in residue):
        return False

    if not tokens:
        return True

    if not (all(t in _ACK_ALLOWED for t in tokens)
            and any(t in _ACK_ANCHORS for t in tokens)):
        return False

    # A decision word remains content regardless of surrounding gratitude.
    if any(t in _DECISION_ANCHORS for t in tokens):
        return False

    # ...and a very short reply still needs an unambiguous gratitude word,
    # so a bare "perfect" or "great" (equally an answer to a question) drafts.
    if len(tokens) <= 2 and not any(t in _GRATITUDE_ANCHORS for t in tokens):
        return False

    return True


def should_draft(message: str, subject: str = "") -> ShouldDraft:
    """Return ok=False only when there is genuinely nothing to answer.

    The subject and the body are judged INDEPENDENTLY and suppression needs
    both to be empty. An email with a blank body and a real subject line
    ("Do you have this in 6-9 months?") is a real question; equally, a thread
    whose subject is "Thanks" must not silence a body that asks something.

    Runs in linear time on the length of the input. Do not reintroduce a
    whole-message regex here — see the note above.
    """
    # ADR-015 §2.4 — collapse padding first; over-limit input drafts, never truncates.
    message = " ".join(str(message or "").split())
    if len(message) > _MAX_GATE_MESSAGE:
        return ShouldDraft(True)
    # Subject and body share the same fail-open-on-length rule.
    subject = " ".join(str(subject or "").split())
    if len(subject) > _MAX_GATE_SUBJECT:
        return ShouldDraft(True)

    if not _carries_no_content(message):
        return ShouldDraft(True)
    if not _carries_no_content(_SUBJECT_NOISE_RE.sub(" ", subject)):
        return ShouldDraft(True)

    combined = f"{subject or ''} {message or ''}"
    if not _strip_decoration(combined).strip():
        return ShouldDraft(False, "empty message")
    return ShouldDraft(False, "no question to answer (thanks/ack only)")
