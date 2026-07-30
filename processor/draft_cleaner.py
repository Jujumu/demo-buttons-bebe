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
    "perfect", "great", "awesome", "excellent", "brilliant", "amazing",
})

# Words that may accompany an acknowledgement without adding a question.
#
# DELIBERATELY SHORT. The previous version listed "there", "problem", "do",
# "yes", "no", "have", "is", "was", "been", "take", "care", "everything" and
# more, so whole complaints and instructions were suppressed: "Ok there is a
# problem", "Yes thanks" (after "shall we cancel?"), "Have you received it".
# The two directions are not symmetric — drafting a reply to a thank-you costs
# one glance, silently dropping a complaint costs a customer — so anything
# that could carry meaning stays OUT of this set.
_ACK_FILLER = frozenset({
    "a", "again", "all", "and", "at", "bye", "dear", "everyone", "folks",
    "for", "from", "guys", "hello", "hey", "hi", "in", "it", "its", "lot",
    "lots", "love", "loved", "lovely", "me", "much", "my", "night", "nice",
    "of", "oh", "on", "regards", "so", "super", "team", "that", "the",
    "this", "to", "too", "u", "very", "we", "weekend", "with", "you",
    "your", "yours", "x", "xx", "xxx",
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
    return text


# ASCII emoticons. ":", "-", "(", ")", "'" and "/" are all inert punctuation,
# so ":(" and ":-(" used to dissolve to nothing and be read as an
# acknowledgement — while the emoji 🙁 was correctly treated as content.
# The (?!/) keeps "https://" out of it.
_EMOTICON_RE = re.compile(r"[:;=8][-'~^]?(?:[()\[\]|\\<>DPpOo3]|/(?!/))")


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

    return (all(t in _ACK_ALLOWED for t in tokens)
            and any(t in _ACK_ANCHORS for t in tokens))


def should_draft(message: str, subject: str = "") -> ShouldDraft:
    """Return ok=False only when there is genuinely nothing to answer.

    The subject and the body are judged INDEPENDENTLY and suppression needs
    both to be empty. An email with a blank body and a real subject line
    ("Do you have this in 6-9 months?") is a real question; equally, a thread
    whose subject is "Thanks" must not silence a body that asks something.

    Runs in linear time on the length of the input. Do not reintroduce a
    whole-message regex here — see the note above.
    """
    if not _carries_no_content(message):
        return ShouldDraft(True)
    if not _carries_no_content(subject):
        return ShouldDraft(True)

    combined = f"{subject or ''} {message or ''}"
    if not _strip_decoration(combined).strip():
        return ShouldDraft(False, "empty message")
    return ShouldDraft(False, "no question to answer (thanks/ack only)")
