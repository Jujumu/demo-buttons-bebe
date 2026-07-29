"""Draft cleaner — last-mile safety pass over the AI's output.

Two functions, imported by processor/hermes_runner.py:

    clean_draft(text: str) -> CleanResult     # runs on the AI DRAFT
    should_draft(message: str) -> ShouldDraft # runs on the CUSTOMER MESSAGE

Ported from the Fable branch (fable/server/app/draft_cleaner.py) unchanged
below this docstring, so the two copies stay diffable.

Fixes the real QA failures:
  QA #01/#04/#10 — the model appends self-commentary ("The response above was
                   complete...") or repeats the entire draft twice (sometimes
                   separated by a blank line, sometimes just a newline).
  QA #19         — an empty customer message got a fabricated reply.

Design notes (why it is built this way):
  * clean_draft() runs on the AI DRAFT, in two conservative passes:
      1. cut trailing self-commentary from the first "self-talk" marker line on;
      2. collapse a draft that is the same content repeated 2x or 3x back to one.
    Both passes are deliberately hard to trigger by accident so a NORMAL reply
    (even one that says the word "complete" or "note" in the middle of a
    sentence) passes through UNCHANGED — see processor/test_draft_cleaner.py.
  * should_draft() runs on the CUSTOMER MESSAGE and returns ok=False when there
    is simply nothing to answer (empty / whitespace / a bare "thanks" / an
    emoji / punctuation). The pipeline must then create NO draft — not a
    fallback one.

Stdlib only (re, dataclasses) so there is nothing new to install on the VPS.

Safety invariant unchanged: this module can only SHORTEN or SUPPRESS a draft.
It can never write, send, or lengthen anything, and a human still clicks send.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Self-talk markers.
#
# Each pattern is anchored to the START of a (stripped) line. When a line begins
# with one of these, that line and EVERYTHING AFTER IT is treated as the model
# talking to itself / the reviewer and is cut. The patterns require the tell-tale
# phrase at the line start, so ordinary prose that merely contains the words
# "complete" or "note" somewhere in a sentence is never affected.
#
# Extend this list as new leak patterns show up in QA.
# ---------------------------------------------------------------------------
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
    # "Note to the reviewer:" / "Note to the team" (self-addressed hand-off).
    # NB: this is NOT "Internal note for human review" (a legit escalation note)
    # — that starts with "internal"/"notes for" and is left untouched.
    r"note to (?:the )?(?:agent|reviewer|team)\b",
    # "End of response" / "[End of draft]"
    r"\[?end of (?:response|reply|draft)\]?",
    # "As an AI, I cannot ..." style refusals leaking into a draft.
    r"as an ai\b.*\bi (?:cannot|can't|am unable)",
]
_MARKER_RE = re.compile(
    r"^[\s>*#\-]*(?:" + "|".join(_SELF_TALK_MARKERS) + r")",
    re.IGNORECASE,
)

# A repeated block must be at least this many normalised characters before we
# treat it as a genuine duplication. Keeps short, legitimately-repeated content
# (e.g. "Yes.\n\nYes.") from being collapsed.
_MIN_DUP_CHARS = 40


@dataclass
class CleanResult:
    text: str
    no_draft: bool = False
    reasons: list[str] = field(default_factory=list)


@dataclass
class ShouldDraft:
    ok: bool
    reason: str = ""


def _cut_self_talk(text: str) -> tuple[str, bool]:
    """Cut everything from the first self-talk marker line onward.

    Returns (possibly-trimmed text, whether anything was cut).
    """
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if _MARKER_RE.match(line.strip()):
            return "\n".join(lines[:i]).rstrip(), True
    return text, False


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
    """If the whole draft is the same content repeated 2x or 3x, keep one copy.

    Works no matter how the copies are separated (blank line, single newline, or
    a single space) because it compares the whitespace-normalised whole text.
    Returns (possibly-shortened text, whether a duplicate was removed).
    """
    stripped = text.strip()
    norm = _normalise(stripped)
    if len(norm) < _MIN_DUP_CHARS:
        return stripped, False

    # Every multiple, not just 2x and 3x. The original tried k in (2, 3) and
    # relied on repeated passes, which reaches 4, 6, 8 and 9 but never a prime
    # multiple: a draft the model wrote five times came out still fivefold.
    # k is bounded by the length floor, so this stays cheap.
    max_k = max(2, len(norm) // _MIN_DUP_CHARS)
    for k in range(2, max_k + 1):
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

    # Iterate to a fixed point. _dedupe_repeats only understands 2x and 3x, so
    # a draft the model wrote four times used to come out still doubled. Four
    # passes collapses any repetition the function can see; the loop always
    # terminates because every pass that changes anything makes `out` strictly
    # shorter.
    for _ in range(4):
        out, cut = _cut_self_talk(out)
        if cut and "stripped model self-commentary" not in reasons:
            reasons.append("stripped model self-commentary")

        out, deduped = _dedupe_repeats(out)
        if deduped and "removed duplicated draft body" not in reasons:
            reasons.append("removed duplicated draft body")

        if not (cut or deduped):
            break

    out = out.strip()
    if not out:
        return CleanResult(
            text="", no_draft=True,
            reasons=reasons + ["nothing left after cleaning"],
        )
    return CleanResult(text=out, no_draft=False, reasons=reasons)


# --- customer-message gate (QA #19) ----------------------------------------
#
# REWRITTEN after code review. The original was a single regex alternation
# matched against the WHOLE message. It had two serious defects:
#
#   1. Exponential backtracking. Multi-word alternatives ("much appreciated",
#      "appreciate it") could also be read as separate tokens, so a failing
#      match explored 2^n paths. A ~350-byte email took over a second; ~700
#      bytes never returned. should_draft() runs synchronously before the
#      first await, so the job timeout could not interrupt it — one email
#      would have frozen the processor permanently.
#   2. It suppressed real messages. Every filler word was its own alternative
#      with no requirement that an actual "thanks" be present, so
#      "So much for the help!" — an angry customer — matched and was silently
#      dropped with no draft and no owner alert.
#
# The replacement is a linear token scan with no backtracking at all, and it
# suppresses ONLY when both conditions hold:
#   * every word is a known acknowledgement or filler word, AND
#   * at least one of them is a real acknowledgement anchor.
# Anything else — any question mark, any unknown word, any angry emoji —
# drafts. When in doubt, draft: a needless draft costs one human glance, a
# silently dropped complaint costs a customer.

# A genuine "this conversation is finished" signal. One of these must be
# present before anything is suppressed.
_ACK_ANCHORS = frozenset({
    "thanks", "thank", "thanx", "thx", "ty", "tysm", "cheers",
    "appreciate", "appreciated", "appreciation",
    "ok", "okay", "kk", "noted", "understood", "received", "got",
    "perfect", "great", "awesome", "excellent", "brilliant",
})

# Words that may accompany an acknowledgement without adding a question.
_ACK_FILLER = frozenset({
    "a", "again", "all", "am", "and", "are", "as", "at", "be", "been", "best",
    "bye", "care", "day", "dear", "do", "everything", "fine", "folks", "for",
    "from", "getting", "good", "goodbye", "guys", "have", "hi", "hello", "hey",
    "i", "im", "is", "it", "its", "lot", "lots", "love", "loved", "lovely",
    "m", "many", "me", "much", "my", "night", "nice", "no", "np", "of", "oh",
    "on", "problem", "really", "regards", "so", "sorry", "super", "take",
    "team", "thats", "the", "then", "there", "this", "to", "too", "u", "very",
    "was", "we", "weekend", "well", "were", "with", "worries", "yall", "you",
    "your", "yours", "youre", "yep", "yes", "yeah",
})

_ACK_ALLOWED = _ACK_ANCHORS | _ACK_FILLER

# Words and digits. Linear, no alternation, no backtracking.
_TOKEN_RE = re.compile(r"[0-9a-z]+")

# Emoji that mean "we are done here". A message made only of these is an ack.
# Anything NOT on this list — including every angry or confused emoji — drafts.
_SAFE_EMOJI = (
    "\U0001F44D", "\U0001F64F", "\u2764\ufe0f", "\u2764", "\U0001F60A",
    "\U0001F642", "\U0001F600", "\U0001F601", "\U0001F970", "\U0001F60D",
    "\U0001F44C", "\u2705", "\U0001F389", "\U0001F495", "\U0001F49B",
    "\U0001F44F", "\U0001F929", "\u2b50", "\U0001F31F",
)

# Punctuation that carries no meaning on its own. Note "?" and "!" are NOT
# here: a bare "?" is a customer chasing an answer, not an acknowledgement.
_INERT_CHARS = " \t\r\n.,~-\u2013\u2014\u2026'\"()"


def should_draft(message: str, subject: str = "") -> ShouldDraft:
    """Return ok=False only when there is genuinely nothing to answer.

    The subject line counts as content: an email with an empty body but a real
    subject ("Do you have this in 6-9 months?") is a real question, and the
    pipeline must still draft for it.

    Runs in linear time on the length of the message. Do not reintroduce a
    whole-message regex here — see the note above.
    """
    text = f"{subject or ''} {message or ''}".strip()
    if not text:
        return ShouldDraft(False, "empty message")

    tokens = _TOKEN_RE.findall(text.lower())

    if not tokens:
        # No letters or digits at all: emoji and/or punctuation.
        residue = text
        for emoji in _SAFE_EMOJI:
            residue = residue.replace(emoji, "")
        residue = residue.strip(_INERT_CHARS)
        if not residue:
            return ShouldDraft(False, "acknowledgement only (emoji/punctuation)")
        # "?", "!", "\U0001F621" and friends are a customer wanting something.
        return ShouldDraft(True)

    if (all(t in _ACK_ALLOWED for t in tokens)
            and any(t in _ACK_ANCHORS for t in tokens)):
        return ShouldDraft(False, "no question to answer (thanks/ack only)")

    return ShouldDraft(True)
