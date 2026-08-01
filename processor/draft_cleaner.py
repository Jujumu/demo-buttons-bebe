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
    # "Note to the reviewer:" USED to be excluded here, because stripping it
    # showed the human a clean, sendable draft and threw away warnings like
    # "do NOT send this, the customer was already refunded twice". That
    # reasoning is now stale: _cut_self_talk RETURNS what it removed and
    # hermes_runner puts it on `reason`, which the console renders. So the
    # warning reaches the reviewer either way, and leaving these in the body
    # meant "this customer has 3 prior chargebacks" sat in the text a human
    # clicks Send on.
    r"notes? (?:to|for) (?:the )?(?:reviewer|agent|human)\b",
    r"^internal\b[:\s]",
    r"for internal use\b",
    r"confidence:\s",
    # "End of response" / "[End of draft]" / "-- end of the draft --"
    #
    # NO leading "[-\s]*" here. _MARKER_RE already prefixes every alternative
    # with "^[\s>*#\-]*", and two adjacent greedy classes whose sets overlap
    # on "-" and whitespace are quadratic: a draft containing a horizontal
    # rule made _MARKER_RE.match take 0.94s at 16 000 dashes and 9.2s at
    # 32 000, with clean_draft the same. That is the happy path - a
    # well-formed, token-tagged model reply - on a synchronous single-process
    # pipeline, so the whole queue stalls.
    #
    # This one was mine: the "[-\s]*" was added in round 8 to catch
    # "-- end of the draft --", and the outer prefix already handled it.
    r"\[?end of (?:the\s+)?(?:response|reply|draft)\]?",
    # Round-8 review: these phrasings all reached the sendable draft body.
    # "The response above is complete." / "The draft above is complete."
    r"(?:the\s+)?(?:response|reply|draft)\s+above\s+(?:is|was)\s+"
    r"(?:already\s+|now\s+)?complete",
    # "Draft complete." / "[Draft complete]"
    r"\[?(?:draft|response|reply)\s+complete\b",
    # "I've completed the draft." / "I have written the response above."
    r"i(?:'ve| have)\s+(?:completed|written|finished)\s+(?:the|this|my)\s+"
    r"(?:response|reply|draft)",
    # An internal note about the customer is not a reply TO the customer.
    # _build_prompt asks for "AGENT NOTE" lines AFTER the verdict, but the
    # model sometimes puts one inside the draft tags - and they carry things
    # like "this customer has 3 prior chargebacks".
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
    # The text that was cut, verbatim. It has to reach the reviewer: some of
    # what the model writes after its draft is a warning ("the billing address
    # does not match the shipping address on this order"), and deciding which
    # by keyword was wrong in both directions.
    removed_note: str = ""


@dataclass
class ShouldDraft:
    ok: bool
    reason: str = ""


def _cut_self_talk(text: str) -> tuple[str, str]:
    """Cut everything from the first self-talk marker line onward.

    Returns (trimmed text, the removed tail) - the tail rather than a bare
    flag, because it has to be shown to the reviewer.

    A keyword veto used to try to KEEP lines that carried a warning
    ("do not send", "fraud", "escalate"). Review broke it in both directions:
    it kept ordinary chatter that happened to contain "careful", and it still
    deleted real warnings that used none of the listed words -

        "The above draft assumes the customer is who they say they are; the
         billing address does not match the shipping address on this order."
        "The above reply promises a replacement we have no stock for - the
         SKU is discontinued."

    There is no keyword list that gets this right, because the property is
    semantic. So the cut is unconditional and the removed text is RETURNED
    instead, to be surfaced next to the draft. Nothing is lost and nothing
    self-congratulatory ends up in the sendable body.
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
    # Largest k first. Returning at the smallest meant each pass only divided
    # the copy count by its smallest prime factor, so 32 copies came out as 2
    # and 64 as 4 even after four passes.
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

    # Iterate to a fixed point. _dedupe_repeats only understands 2x and 3x, so
    # a draft the model wrote four times used to come out still doubled. Four
    # passes collapses any repetition the function can see; the loop always
    # terminates because every pass that changes anything makes `out` strictly
    # shorter.
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


# ASCII emoticons. ":", "-", "(", ")", "'" and "/" are all inert punctuation,
# so ":(" and ":-(" used to dissolve to nothing and be read as an
# acknowledgement — while the emoji 🙁 was correctly treated as content.
# The (?!/) keeps "https://" out of it.
# Only the SAD mouths count as content. The first version included ")", "D",
# "P", "o" and "3", so every happy sign-off - "thanks :)", "thank you :D" -
# was forced to draft.
_EMOTICON_RE = re.compile(r"[:;=8][-'~^]?(?:[(\[|\\<]|/(?!/))")

# ...and the happy ones are stripped like an emoji, so their mouth character
# does not survive as a stray token ("thank you :D" tokenised a bare "d").
_HAPPY_EMOTICON_RE = re.compile(r"[:;=8][-'~^]?[)\]>DdPpOo3*]+")


# Noise every email subject carries. Without stripping it the subject veto
# fired on essentially every real ticket ("Re: Your Buttons Bebe order
# #10234"), so this gate never actually ran in production - measured at 0 of
# 15 acknowledgements suppressed with a realistic subject line.
#
# "\border[\s#]*\d+", NOT "\border\s*#?\s*\d+". Two \s* separated by an
# optional #? is quadratic: for a subject that is the word "order" followed by
# a long whitespace run and no digit, the engine tries every way of splitting
# the run between the two groups. Measured on the version with two groups:
# 8 000 spaces 0.80 s, 16 000 2.93 s, 32 000 11.64 s, 128 000 ~3 minutes.
#
# That is not a slow request, it is a stopped shop. should_draft() runs
# SYNCHRONOUSLY inside the job coroutine, so asyncio.wait_for cannot interrupt
# it - verified: wait_for(job(), timeout=1.0) returned normally after 6.5 s -
# and orchestrator.py holds an exclusive flock, so there is exactly one
# processor. One email with a padded subject line freezes every ticket, every
# owner alert and the heartbeat until it finishes.
#
# This is the SECOND time this file has had that bug. The note further down
# describes the first (an exponential alternation, ~700 bytes never returned);
# the fix for it left this quadratic behind in a pattern added afterwards.
# A single character class cannot backtrack, so there is nothing left to split.
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

    # A DECISION word is content however much gratitude surrounds it.
    #
    # "ok", "noted", "received", "got it" are answers to a question the agent
    # just asked - "shall I cancel order #10234 before it ships?" - and
    # suppressing them stores an empty card and ships the order. The first
    # version of this guard was length-based ("<= 2 tokens without gratitude"),
    # which review broke in one word: "ok thanks" has a gratitude anchor so
    # the guard never fired, and "got it thanks" is three tokens so it did not
    # apply at all. Both were suppressed. The property has nothing to do with
    # length, so it is no longer expressed as a length.
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
    # Bound the input as well as fixing the pattern.
    #
    # The regex fix removes the known quadratic, but this gate runs
    # synchronously on the one processor the shop has, so a bug here stops the
    # business rather than slowing it. Two independent defences, because this
    # file has now had two catastrophic-backtracking bugs and the second was
    # introduced by the fix for the first.
    #
    # "Truncating cannot lose a decision" was WRONG, and it was my own
    # justification. Truncation REMOVES content, so the reasoning runs the
    # other way: an ack that fills the cap hides whatever follows it.
    #
    #     ("thanks " * 2857) + "Also, my parcel has been sitting at the depot
    #     since Tuesday and nobody has called me back."
    #
    # was suppressed - empty console card, no send controls, no owner alert,
    # Hermes never invoked, complaint never read.
    #
    # So: collapse whitespace FIRST, so padding cannot fill the budget, and
    # then refuse to judge anything still over it. "I could not read all of
    # this" is not the same as "there is nothing here", and only the second
    # justifies silence.
    message = " ".join(str(message or "").split())
    if len(message) > _MAX_GATE_MESSAGE:
        return ShouldDraft(True)
    # The SUBJECT gets the same treatment, three lines after declaring that
    # reasoning wrong. Round 10: the body was fixed and this slice was not, so
    #   subject = ("thanks " * 286) + "Why has my refund still not arrived?"
    # was suppressed at 2 038 characters and drafted at 1 996 - the question
    # fell off the end of the slice. The classifier still escalates and pages
    # the owner from the raw subject, so the blast radius is a missing draft
    # rather than a missing alert, but it is the same mistake.
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
