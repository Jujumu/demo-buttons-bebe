"""Ticket priority classifier — deterministic first-pass screen.

Runs BEFORE Hermes as an advisory safety net. If the classifier flags a
ticket as sensitive, the orchestrator treats it as sensitive even if the
LLM misclassifies it. The classifier can only ESCALATE (NORMAL → HIGH/
IMMEDIATE), never de-escalate the LLM's assessment.

Classification logic:
  IMMEDIATE — refunds, chargebacks, disputes, wrong/damaged items,
              angry customers, order value > $200 with complaint.
              → Sensitive, notify owner.
  HIGH      — urgent shipping, final sale exceptions, address changes,
              sizing/fabric unknown, cancellations.
              → Sensitive (if applicable), notify owner.
  NORMAL    — shipping status, pickup questions, sizing help (info available),
              exchange requests, promo codes, general product questions.
              → Standard draft.

The classifier uses keyword matching on the message text + Gorgias intent
names + KB sensitivity flags. It does NOT call any external APIs — it is
purely deterministic and runs in <1ms.

Ported from the Fable branch (Task 4 of the Fable port), RULES ONLY:
  * a "demanding a manager" category, which main had no rule for at all;
  * structural anger — three or more "!!!" and ALL-CAPS shouting — so a message
    with no angry *word* can still escalate;
  * wrong-item phrasings that contain no literal "wrong";
  * extra damage, missing-item, non-delivery, fraud, dispute and legal phrases,
    including British spellings.
Fable's deploy/vps-patches/classifier.py was deliberately NOT copied over it:
that file targets a stub this module has long since replaced, returns capitalised
priorities, and does not import get_settings/log_event.

Every verdict also carries "matched" — the literal phrases that fired — so a
surprising escalation can be explained from the log without re-reading the
regex tables. Run `python classifier.py` for the built-in labelled self-test.
"""

from __future__ import annotations

import re
from typing import Any

from config import get_settings
from logging_setup import get_logger, log_event

logger = get_logger(__name__)

# Priority constants
IMMEDIATE = "immediate"
HIGH = "high"
NORMAL = "normal"

# ── Keyword patterns ────────────────────────────────────────

# IMMEDIATE: money/dispute/damage/angry — always sensitive
#
# MAIN'S ORIGINAL TABLE. Everything in here is evaluated on the UNFILTERED
# text, exactly as main evaluated it. Nothing this port added may narrow the
# input these rules see, or the port could classify LOWER than main - the one
# outcome it is not allowed to have. See classify() for the two views.
_MAIN_IMMEDIATE_KEYWORDS = [
    # Refunds and money
    r"\brefund\b", r"\bchargeback\b", r"\bdispute\b", r"\bmoney\s+back\b",
    r"\breimburse\b", r"\breimbursement\b", r"\bcompensat\w*\b",
    r"\bcredit\s+(my|your|our)\s+account\b", r"\bissue\s+a\s+refund\b",
    r"\breturn\s+(my|the)\s+(money|payment|funds)\b",
    # Damaged/wrong/missing items
    r"\bdamaged?\b", r"\bdefect\w*\b", r"\bbroken\b", r"\btorn\b",
    r"\bwrong\s+(item|size|color|colour|product|order)\b",
    r"\bmissing\s+(item|piece|part|product)\b",
    r"\bnever\s+(received|arrived|came|got)\b",
    r"\bdidn'?t\s+(receive|get|arrive)\b", r"\bnot\s+received\b",
    r"\blost\s+(package|parcel|order|shipment)\b",
    r"\bstolen\s+(package|parcel|order|shipment)\b",
    r"\b(package|parcel|order|shipment)\s+(?:was|is|got|has\s+been)\s+(lost|stolen)\b",
    # Angry/abusive
    r"\b(angry|furious|outraged|disgusted|appalled|unacceptable)\b",
    r"\b(terrible|horrible|awful|worst)\s+(service|experience|company|store)\b",
    r"\bnever\s+(shopping|buying|ordering)\s+(here|from\s+you)\b",
    r"\b(bbb|better\s+business\s+bureau|consumer\s+protection|small\s+claims)\b",
    r"\b(lawsuit|sue|legal\s+action|attorney|lawyer)\b",
    # Fraud
    r"\bfraud\b", r"\bscam\b", r"\bunauthorized\s+charg\w+\b",
]

# ── Ported from the Fable branch (rules only — Task 4 of the port).
# Only phrases that are UNAMBIGUOUS in a support inbox go in this list;
# the merely-suggestive ones live in _WEAK_IMMEDIATE below and need
# corroborating context before they fire. See the note above that list.
#
# Kept as a SEPARATE table because these - and only these - are evaluated on
# the boilerplate-filtered view of the message. Filtering exists to stop the
# store's own footer ("if an item is missing from your parcel, reply to this
# email") from firing the new rules; it must never be allowed to hide text
# from main's rules above.
_PORT_IMMEDIATE_KEYWORDS = [
    # Chargeback / payment-reversal phrasings main missed
    r"\bcharge\s?-?\s?back\b", r"\bcharged\s+back\b",
    r"\breverse\s+the\s+(charge|payment)\b",
    r"\bdisput(?:ing|ed)\b", r"\bcontest\s+the\s+charge\b",
    r"\b(?:did\s+not|didn'?t|never|have\s+not|haven'?t)\s+authoris?z?e\w*\b",
    r"\bunauthoris(?:ed|ing)\s+(charge|transaction|payment)\b",
    r"\bunauthorized\s+transaction\b",
    # Fraud / theft accusations
    r"\bfraudulent\b", r"\bscamm(?:ed|er)\b", r"\brip\s?off\b",
    r"\bripped\s+me\s+off\b", r"\bstole\s+my\s+money\b",
    r"\b(?:want|give\s+me|return)\s+my\s+money\b",
    r"\byou\s+stole\b", r"\btheft\b",
    # Legal / regulatory variants
    r"\bsuing\b", r"\blegal\s+counsel\b", r"\bcease\s+and\s+desist\b",
    r"\bfile\s+a\s+complaint\b",

    # Wrong item — phrasings that contain no literal "wrong"
    r"\b(?:is\s?n'?t|was\s?n'?t|not)\s+what\s+i\s+ordered\b",
    r"\b(?:got|sent|received)\s+the\s+wrong\b",
    r"\bnot\s+mine\b", r"\bnot\s+as\s+described\b",
    r"\blooks?\s+nothing\s+like\b",
    r"\bnothing\s+like\s+the\s+(photo|picture|listing|description|website)\b",
    # NB the article is REQUIRED. With it optional, "but got" matched
    # "it shipped late but got here safely" — a compliment.
    r"\bbut\s+(?:i\s+)?got\s+(?:a|an|the)\s",
    r"\bbut\s+received\s+(?:a|an|the)\s",
    r"\binstead\s+i\s+got\b",
    # "You sent a different item" is a shipment claim; "I ordered from you last
    # year and lost the code" is purchase history. Only the first is evidence,
    # so the verb needs a wrong/different object rather than sitting in
    # _ORDER_CONTEXT_RE where it unlocked the whole omission table.
    # The whitespace goes INSIDE the optional group. "(?:a|an|the)?\s*" is
    # quadratic, and this table runs on EVERY ticket with no gate in front of
    # it: "you sent" + 59 000 spaces took 12.9s, and 52s with the subject
    # amplifying it.
    #
    # "\s*" inside, not "\s+". The first attempt used \s+ and was NARROWER -
    # it stopped matching "you sent me thewrong item", a typo form the old
    # pattern caught, which is a de-escalation. 54 such strings turned up in
    # the equivalence check. With \s* inside the group the language is
    # identical (0 differences over 300 000 probes) and the backtracking is
    # still gone, because after the first \s+ gives back a character the
    # optional group either matches an article immediately or fails.
    r"\byou\s+(?:sent|shipped|packed)\s+(?:me\s+)?(?:(?:a|an|the)\s*)?"
    r"(?:wrong|different|completely\s+different)\b",

    # Damage reported as a fact about a received item.
    r"\bcracked\b", r"\bshattered\b", r"\bfrayed\b", r"\bfell\s+apart\b",
    r"\bseam\s+ripped\b",
    # "has/have/had" alone are too weak here: "Do you have a tear-away label?"
    # is a product question, not a damage report. Require a reporting subject,
    # and never match the compound "tear-away".
    r"\b(?:there\s?'?s|there\s+is|it\s+has|it\s+had|came\s+with|"
    r"arrived\s+with|turned\s+up\s+with|found)\s+(?:a\s+)?(?:big\s+|small\s+|"
    r"large\s+|huge\s+|tiny\s+)?(?:hole|rip|tear|stain|snag)\b(?!\s*(?:-\s*)?away)",

    # Missing / undelivered, phrased unambiguously
    r"\b(?:did\s+not|didn'?t)\s+come\s+with\b",
    r"\b(?:marked|says|shows|tracking\s+says)\s+(?:it\s+was\s+|as\s+)?delivered\s+but\b",
    r"\bnothing\s+(?:is\s+)?here\b",
]

# One name for anything that wants the whole table (the mutation harness in
# processor/test_classifier_rules.py, for one). classify() deliberately does
# NOT use this: it runs the two halves against two different views.
_IMMEDIATE_KEYWORDS = _MAIN_IMMEDIATE_KEYWORDS + _PORT_IMMEDIATE_KEYWORDS

# ── Weak triggers: only a complaint IN CONTEXT ──────────────
# Every phrase here is ordinary English that a browsing customer uses all the
# time. Code review of the first version of this port measured 13 out of 13
# realistic benign messages escalating — 11 of them to IMMEDIATE, which pages
# the owner's phone. "Can I order the romper without the bow?",
# "How do I get a stain out of a cotton onesie?", "I'm a bit lost, which size
# do I need?" were all treated as emergencies.
#
# These now fire ONLY when the message also shows evidence of an order that
# has been placed or delivered, and is not phrased as a browsing or care
# question. A genuine complaint always carries that evidence; a pre-sale
# question almost never does.
# Damage evidence. Nobody says "arrived ripped" while browsing, so these need
# order context but are NOT blocked by a browsing-shaped question: "Do you sell
# a replacement bow? Mine arrived ripped." is a complaint.
_WEAK_DAMAGE = [
    r"\bripped\b", r"\bstained\b",
    # "(?!\s*(?:-\s*)?away)", NOT "(?!\s*-?\s*away)". Same quadratic as
    # _ORDER_CONTEXT_RE, hidden inside a lookahead: two \s* separated by an
    # optional "-" lets the engine split a whitespace run every possible way.
    # "a hole" + 100 000 spaces took 17.6s. Rewritten so the first \s* is
    # followed by a single-character decision, it is 0.0013s - and 0.028s on
    # 2 MB. Exactly equivalent: checked over 300 000 random probes plus every
    # hyphen and whitespace arrangement of "tear-away", 0 differences.
    r"\ba\s+(?:hole|rip|tear|stain)\b(?!\s*(?:-\s*)?away)",
    r"\b(?:hole|rip|tear|stain)\s+(?:in|on)\b",
    r"\banother\s+customer\b",
    r"\bsomeone\s+else'?s?\s+(order|name|items?|package|parcel|box)\b",
]

# Omission wording. These ARE how customers word a purchase request - "can I
# order the romper without the bow?" - so they stay behind the browsing guard.
_WEAK_OMISSION = [
    r"\bmissing\b",
    r"\blost\b",
    r"\bwithout\s+the\b",
    r"\bnot\s+included\b", r"\bwas\s?n'?t\s+included\b",
    r"\bleft\s+out\b", r"\bsupposed\s+to\s+include\b",
    r"\bdifferent\s+item\b", r"\binstead\s+of\s+the\b",
]

# Kept as one name for the mutation tests and for anything that iterates them.
_WEAK_IMMEDIATE = _WEAK_DAMAGE + _WEAK_OMISSION

# Evidence that this is about a real order, not a pre-sale question.
_ORDER_CONTEXT_RE = re.compile(
    r"\b("
    r"arrived|delivered|delivery|received|came\s+(?:in|today|yesterday)|"
    r"parcel|parcels|package|packages|shipment|the\s+box|my\s+box|in\s+the\s+box|"
    r"tracking|courier|dispatched|"
    r"my\s+(?:order|purchase|item|items|delivery|parcel|package)|"
    # "order[\s#]*\d", NOT "order\s*#?\s*\d". Two \s* separated by an optional
    # #? is quadratic: for "order" followed by a long whitespace run and no
    # digit, the engine tries every way of splitting the run between the two
    # groups. Measured: 3.1s on a 40 000-char message, and classify() took
    # 4.05s end to end. The classifier runs synchronously on the single
    # processor, so that is a stalled queue - no drafts, no owner alerts -
    # for as long as such emails keep arriving.
    #
    # The identical bug was found in draft_cleaner._SUBJECT_NOISE_RE in the
    # same review. A single character class cannot backtrack.
    r"order[\s#]*\d|#\s*\d{3,}"
    r")\b",
    re.IGNORECASE,
)

# Shapes that mean "I am asking about buying or caring for something", which
# suppress the weak triggers even when an order word happens to appear.
_BROWSING_QUESTION_RE = re.compile(
    r"\b(can\s+i|could\s+i|do\s+you|does\s+the|does\s+it|is\s+there|are\s+there|"
    r"am\s+i|how\s+do\s+i|how\s+can\s+i|how\s+to|how\s+would\s+i|"
    r"what'?s?\s+the\s+best\s+way|any\s+tips|is\s+it\s+possible|would\s+it\s+be)\b",
    re.IGNORECASE,
)


# A polite complaint is still a complaint. "Is it possible the courier lost my
# parcel? Tracking stopped 8 days ago." opens with a browsing marker but is
# plainly a delivery problem, so these indicators lift the browsing guard.
_PROBLEM_CONTEXT_RE = re.compile(
    r"\b(tracking|courier|carrier|still\s+waiting|still\s+not|no\s+update|"
    r"has\s?n'?t\s+moved|has\s+not\s+moved|"
    r"where\s+is|where\s+are|chasing|chase\s+this|follow(?:ing)?\s?up|"
    r"never\s+(?:came|arrived|turned\s+up)|"
    # "why" turns a polite request into a complaint: "Can I ask why my order
    # came without the hat?"
    r"why\b|"
    # NO bare durations. In a baby-clothes store "my 6 week old" and "it
    # arrived 3 days ago and it is lovely" are ordinary sentences; any
    # duration alternative turns them into an owner page. Waiting has to be
    # said out loud.
    r"still\s+(?:has\s?n'?t|have\s?n'?t|no|nothing)|"
    # "(?:(?:\d+|a|two|three)\s*)?", NOT "(?:\d+|a|two|three)?\s*". The \s
    # must be INSIDE the optional group, so a single-character decision
    # follows the first \s+. Otherwise the engine splits a whitespace run
    # every possible way: 128 000 chars took 227 SECONDS, and one ticket
    # stalled classify() for 204s.
    #
    # This does not need an attacker. \s matches U+00A0, which is what every
    # HTML-to-text converter emits for padded table cells, so an ordinary
    # marketing-styled reply reproduces it: "I have been waiting" + 30 000
    # non-breaking spaces + "for my order 10322" took 13.2s.
    r"(?:waiting|waited)\s+(?:for\s+)?(?:over\s+)?(?:(?:\d+|a|two|three)\s*)?"
    r"(?:days?|weeks?|months?)|"
    r"been\s+(?:over\s+)?(?:\d+|two|three|four)\s*(?:days?|weeks?|months?))",
    re.IGNORECASE,
)


def _weak_matches(text: str) -> list[str]:
    """Weak triggers that are allowed to escalate for this message.

    Both classes need evidence of a real order. Damage evidence then fires
    regardless of how the sentence is shaped; omission wording additionally
    has to survive the browsing guard, because "without the bow" and "a
    different item" are how customers word a purchase request.
    """
    if not _ORDER_CONTEXT_RE.search(text):
        return []

    found = _find_matches(text, _WEAK_DAMAGE)

    browsing = (_BROWSING_QUESTION_RE.search(text)
                and not _PROBLEM_CONTEXT_RE.search(text))
    if not browsing:
        found.extend(m for m in _find_matches(text, _WEAK_OMISSION)
                     if m not in found)
    return found


# Demanding a manager / refusing to deal with support. Main had NO rule for
# this whole category — these tickets are angry and should always escalate.
_MANAGER_DEMAND_KEYWORDS = [
    r"\b(?:speak|talk)\s+to\s+(?:a|your|the)\s+(?:manager|supervisor|owner)\b",
    r"\bget\s+me\s+(?:a|your|the)\s+(?:manager|supervisor|owner)\b",
    r"\bwant\s+(?:a|to\s+speak\s+to\s+a)\s+manager\b",
    r"\byour\s+supervisor\b",
    r"\bi\s+demand\b",
    # Trying to route around support entirely.
    r"\b(?:owner|manager|supervisor)'?s?\s+(?:personal\s+)?"
    r"(?:phone|number|cell|mobile|email|address)\b",
]

# "please don't escalate this, I just have a quick question" is the opposite
# of an escalation demand, so this one needs a negation guard.
_ESCALATE_RE = re.compile(r"\bescalate\s+(?:this|my)\b", re.IGNORECASE)
_ESCALATE_NEGATED_RE = re.compile(
    r"\b(?:do\s?n'?t|do\s+not|no\s+need\s+to|not?\s+need|rather\s+not|"
    r"please\s+do\s?n'?t)\s+(?:\w+\s+){0,2}escalate\b",
    re.IGNORECASE,
)

# HIGH: urgent/time-sensitive — may or may not be sensitive
#
# MAIN'S ORIGINAL TABLE — evaluated on the UNFILTERED text, as main did.
_MAIN_HIGH_KEYWORDS = [
    r"\burgent\b", r"\basap\b", r"\brush\b", r"\bexpress\b",
    r"\bneed\s+(it|them)\s+(by|before|tomorrow|today|monday|tuesday|wednesday|thursday|friday)\b",
    r"\bdeadline\b", r"\btime\s+sensitive\b",
    # Address changes (time-critical if before shipment)
    r"\bchange\s+(my\s+)?(shipping\s+)?address\b", r"\bwrong\s+address\b",
    r"\bupdate\s+(my\s+)?address\b", r"\bnew\s+address\b",
    # Cancellations
    r"\bcancel\s+(my\s+)?(order|item|purchase)\b", r"\bcancellation\b",
    # Final sale exceptions
    r"\bfinal\s+sale\b", r"\bno\s+returns?\b",
    # Not received (general)
    r"\bwhere\s+is\s+my\s+(order|package|parcel)\b",
    r"\b(haven'?t|have\s+not)\s+(received|gotten|seen)\b",
    r"\bnot\s+yet\s+(received|arrived|delivered)\b",
    r"\blast\s+(chance|warning)\b",
    # (The multi-follow-up rule lives in _FOLLOWUP_PATTERN, which is applied to
    # a bounded slice: its ".*" is the one pattern here that backtracks.)
]

# ── Ported from Fable (Task 4). Non-delivery phrasings main missed.
# These sit at HIGH, not IMMEDIATE: "I still haven't received it" is the
# single most common where-is-my-order wording, and routing every WISMO to
# the owner's phone would bury the alerts that matter. Outright theft
# signals ("never arrived", "marked delivered but") stay IMMEDIATE above.
# Main covered only the singular "hasn't received"; the plural forms and
# "hasn't arrived" fell all the way to NORMAL.
#
# Like _PORT_IMMEDIATE_KEYWORDS, these - and only these - see the
# boilerplate-filtered view of the message.
_PORT_HIGH_KEYWORDS = [
    r"\b(?:has\s?n'?t|has\s+not|have\s+not|have\s?n'?t)\s+(?:arrived|turned\s+up|shown\s+up)\b",
    r"\bstill\s+(?:has\s?n'?t|have\s?n'?t|not)\s+(?:arrived|come|received)\b",
    r"\bnot\s+(?:been\s+)?delivered\b",
    r"\bnothing\s+(?:has\s+|had\s+)?(?:arrived|come|turned\s+up|showed\s+up|been\s+delivered)\b",
    # Main only had the "where is my order" word order.
    r"\bwhere\s+my\s+(?:order|parcel|package|delivery|items?|stuff)\s+(?:is|are)\b",
]

# One name for anything that wants the whole table. classify() deliberately
# does NOT use this: it runs the two halves against two different views.
_HIGH_KEYWORDS = _MAIN_HIGH_KEYWORDS + _PORT_HIGH_KEYWORDS

# The subset of _HIGH_KEYWORDS this port added. Kept as its own tuple purely so
# processor/test_classifier_rules.py can mutation-test them like the others.
# DERIVED, not retyped: the hand-copied version silently drifted out of sync
# with the table the first time a pattern was edited.
_PORTED_HIGH_PATTERNS = tuple(_PORT_HIGH_KEYWORDS)

# Intent names that indicate sensitive topics
_SENSITIVE_INTENTS = {
    "order/wrong", "order/missing", "order/damaged",
    "refund", "refund/request", "chargeback", "dispute",
    "cancel", "cancellation", "address-change",
    "payment-error", "payment-dispute",
}

# Intent names that indicate high urgency
_HIGH_INTENTS = {
    "urgent", "rush", "cancel", "cancellation",
    "address-change", "final-sale-exception",
}

_HIGH_SENSITIVE_INTENTS = {
    "cancel", "cancellation", "address-change", "final-sale-exception",
}

# MAIN'S ORIGINAL — evaluated on the UNFILTERED text, as main did.
_MAIN_HIGH_SENSITIVE_PATTERN = re.compile(
    r"\b(final\s+sale|change\s+(?:my\s+)?(?:shipping\s+)?address|"
    r"wrong\s+address|update\s+(?:my\s+)?address|new\s+address|"
    r"cancel(?:lation)?(?:\s+(?:my\s+)?(?:order|item|purchase))?)\b",
    re.IGNORECASE,
)

# Main's rules plus this port's. Evaluated on the filtered view; classify()
# ORs it with _MAIN_HIGH_SENSITIVE_PATTERN so filtering can only ever add.
_HIGH_SENSITIVE_PATTERN = re.compile(
    r"\b(final\s+sale|change\s+(?:my\s+)?(?:shipping\s+)?address|"
    r"wrong\s+address|update\s+(?:my\s+)?address|new\s+address|"
    r"cancel(?:lation)?(?:\s+(?:my\s+)?(?:order|item|purchase))?|"
    # Non-delivery (ported, Task 4). CLAUDE.md lists undelivered orders as a
    # sensitive category: the model must not promise a delivery date or a
    # replacement, so the draft has to be flagged for careful review even
    # though the tier stays HIGH rather than IMMEDIATE.
    r"(?:has\s?n'?t|has\s+not|have\s+not|have\s?n'?t)\s+(?:arrived|turned\s+up|shown\s+up)|"
    r"still\s+(?:has\s?n'?t|have\s?n'?t|not)\s+(?:arrived|come|received)|"
    r"nothing\s+(?:has\s+|had\s+)?(?:arrived|come|turned\s+up|showed\s+up|been\s+delivered)|"
    r"not\s+(?:been\s+)?delivered)\b",
    re.IGNORECASE,
)

# Angry indicator keywords.
#
# The old comment here said "if 2+ angry keywords, force IMMEDIATE". It does
# not, and never did - on main either. The angry_hits test in classify() sits
# INSIDE the IMMEDIATE branch, so by the time it runs the verdict is already
# IMMEDIATE and all it does is add a line to the reason string. Round 6
# confirmed it by mutation: raising the threshold to 99 changes no verdict.
#
# Left as main had it. Making it load-bearing would escalate messages main
# left at HIGH ("this is terrible and awful"), and every new escalation is a
# push notification to the owner's phone - out of scope for a port whose rule
# is "same or higher, and no new false alarms". See
# AngryThresholdIsNotLoadBearingTests, which pins the real behaviour so the
# next reader does not trust the label either.
_ANGRY_KEYWORDS = [
    r"\b(angry|furious|outraged|disgusted|appalled|unacceptable)\b",
    r"\b(terrible|horrible|awful|worst)\b",
    r"\bnever\s+(shopping|buying|ordering)\s+(here|from\s+you)\b",
    r"\b(bbb|better\s+business\s+bureau|consumer\s+protection|small\s+claims)\b",
    r"\b(lawsuit|sue|legal\s+action|attorney|lawyer)\b",
    r"\b(scam|fraud|rip\s?off|robbed)\b",
]

# Repeated follow-up pattern (3+ messages, no reply)
_FOLLOWUP_PATTERN = re.compile(
    r"(following\s+up|follow\s?up|still\s+(no|waiting)|yet\s+again|"
    r"any\s+(update|response|reply|answer)|"
    r"(2nd|3rd|second|third|fourth)\s+(time|attempt|message|email|follow))",
    re.IGNORECASE,
)


# ── Structural anger (ported from Fable, reworked after review) ─────
# Main only counted angry *words*. These catch shouting that uses none.
# The first version escalated "Thank you so much!!! The dress is perfect!!!"
# and "Do you carry NUNA UPPABABY BUGABOO DOONA CYBEX?" — both of which page
# the owner's phone — while missing "I WANT MY MONEY NOW".

_EXCLAIM_RE = re.compile(r"!{3,}")

_POSITIVE_RE = re.compile(
    r"\b(thank|thanks|thankyou|thx|love|loved|loving|adorable|perfect|beautiful|"
    r"gorgeous|cute|amazing|wonderful|excellent|obsessed|delighted|thrilled|"
    r"pleased|happy|brilliant|fantastic|lovely|great|awesome|best|nice|super|"
    r"fab|fabulous|appreciate|appreciated|recommend|quick|fast|impressed|"
    # Added after a review measured 6 of 20 grateful all-caps messages paging
    # the owner. Every word below came from one of them; the vocabulary of
    # praise for baby clothes is not the vocabulary the first list assumed.
    r"worth|favourite|favorite|soft|softer|softest|comfy|cosy|cozy|snug|"
    r"cutest|recommended|glad|happier|happiest|adore|adored|stunning|"
    r"well\s+spent|every\s+penny)\b",
    re.IGNORECASE)
# Grievance words only. The first version listed "not", "no" and "still", which
# are in half of all English sentences - one stray "no notes!" re-armed the
# exclamation rule and paged the owner about a compliment.
#
# "never" is NOT a bare entry. "I have never been happier", "still my
# favourite", "I will never shop anywhere else" are praise, and treating the
# word alone as a grievance cancelled the positive veto on all of them. It
# counts only with a complaint continuation, or with a "never ... again".
# The genuine misses this could create are all covered by keyword rules that
# do not consult this pattern at all ("never received", "never arrived").
_NEGATIVE_RE = re.compile(
    r"\b(never\s+(?:received|receive|arrived|arrive|came|come|got|get|"
    r"turned\s+up|show(?:ed|n)\s+up|delivered|deliver|shipped|ship|sent|send|"
    r"replied|reply|responded|respond|answered|answer|heard|resolved|"
    r"refunded|works?|worked|shopping|buying|ordering|using)|"
    r"never\s+(?:\w+\s+){0,3}again|"
    r"refund|damaged|broken|wrong|missing|late|angry|furious|"
    r"unacceptable|terrible|awful|worst|horrible|disappointed|disappointing|"
    r"ridiculous|useless|rubbish|scam|fraud|cancel|complaint|complain|"
    r"nobody|noone|ignored|ignoring|refused|refusing|disgusting|disgrace|"
    r"appalling|pathetic|unhappy|fed\s+up|sick\s+of|had\s+enough|"
    # Balance for the praise words added above: "worth" is positive, but
    # "not worth it" and "waste of money" are not.
    r"n[o']?t\s+worth|waste|wasted|poor\s+quality|bad\s+quality|"
    r"cheap\s+quality|falling\s+apart|"
    # Round 6: 13 of 20 realistic all-caps complaints stayed NORMAL because
    # this list had no word for how people actually express annoyance. None
    # of them was a regression against main - main misses them too - but the
    # structural-anger rule exists precisely to catch shouting that uses no
    # angry *word* from main's table, and it was being vetoed by a single
    # stray "glad" or "worth".
    r"shocking|shockingly|disgraceful|frustrat\w+|livid|fuming|seething|"
    r"appalled|outrage\w*|no\s+(?:reply|response|answer|word|update)|"
    r"chasing|wits\s+end|joke|shambles|fiasco|third\s+time|3rd\s+time)\b",
    re.IGNORECASE)

# Quoted email history dilutes every ratio, so measure the new text only.
# Matched per LINE. Truncating at the first marker returned an empty string for
# every bottom-posted or inline reply - Outlook's default - which silently
# disabled both structural signals.
_QUOTE_LINE_RE = re.compile(r"^\s*(?:>|\|)")
# "wrote:" must END the line. Otherwise "Your colleague wrote: we will chase
# it. THIS IS RIDICULOUS!!!" - the customer's own prose - was discarded.
_QUOTE_HEADER_RE = re.compile(
    r"^\s*(?:"
    # A real "On <date> <someone> wrote:" header contains a date, so requiring
    # a digit distinguishes it from the customer's own prose - "On Friday I
    # ordered a gift set. Your colleague wrote: ..." must NOT be discarded.
    # The trailing text is allowed because Gmail puts it on the same line.
    r"on\s.{0,200}\d.{0,160}\swrote:"
    # Bounded character classes. The original "<[^>]+@[^>]+>" nested two
    # unbounded quantifiers and took 72 SECONDS on a 512KB line - 226x main,
    # which has no such pattern at all.
    r"|.{0,120}<[^>@\s]{1,64}@[^>\s]{1,64}>\s+wrote:"
    r"|-{2,}\s*(?:original message|forwarded message)"
    r"|begin\s+forwarded\s+message:"
    r"|_{5,}\s*$"
    r"|(?:from|sent|to|subject):\s.{0,200}$"
    r")",
    re.IGNORECASE)

_CAPS_WORD_RE = re.compile(r"\b[A-Z]{2,}\b")
_WORD_RE = re.compile(r"\b[A-Za-z]{2,}\b")

# All-caps tokens that are information, not shouting.
_CAPS_STOPWORDS = frozenset({
    "USPS", "UPS", "DHL", "FEDEX", "USA", "UK", "EU", "CAD", "USD", "GBP",
    "ASAP", "VAT", "GST", "PST", "EST", "CST", "MST", "UTC", "PDT", "EDT",
    "COD", "PIN", "SKU", "FAQ", "URL", "PDF", "OMG", "AM", "PM", "ID", "OK",
    "THE", "AND", "FOR", "YOU", "ARE", "WAS", "BUT", "NOT", "ALL", "ANY",
    "CAN", "GET", "HAS", "HAD", "MY", "ME", "IT", "IS", "IN", "ON", "TO",
    "OF", "AT", "SO", "IF", "OR", "DO", "BE", "BY", "UP", "NO",
})

# A caps message only counts as shouting if at least one SHOUTED word is a
# grievance word. Brand lists and pasted addresses are all caps too.
# GRIEVANCE words only. The first version listed WHY, WHAT, HOW, PLEASE, HELP,
# THIS, THAT, YOUR, WANT and NEED, so any caps-lock question escalated:
# "DO YOU SHIP TO CANADA AND HOW MUCH IS IT" and "PLEASE SEND ME THE SIZE
# CHART" both paged the owner. Caps lock is a habit; anger is a word choice.
_SHOUT_ANCHORS = frozenset({
    "NEVER", "STILL", "UNACCEPTABLE", "RIDICULOUS", "TERRIBLE", "AWFUL",
    "WORST", "HORRIBLE", "JOKE", "SERIOUSLY", "ENOUGH", "SICK", "TIRED",
    "FED", "USELESS", "APPALLING", "DISGRACE", "DISGUSTING", "PATHETIC",
    "ANGRY", "FURIOUS", "NOBODY", "IGNORING", "IGNORED",
    "REFUND", "MONEY", "SCAM", "FRAUD", "LAWYER", "DEMAND", "COMPLAINT",
    "WRONG", "BROKEN", "DAMAGED", "MISSING", "CANCEL", "IMMEDIATELY",
    "ANSWER", "ANSWERED", "REPLY", "RESPOND", "RESPONSE", "WAITING",
    "PHONE", "MANAGER", "SUPERVISOR", "URGENT",
    # Round 6. Unambiguous grievance nouns with no praise use at all, so they
    # are safe to add to both this set and the HARD set below.
    "SHOCKING", "DISGRACEFUL", "LIVID", "FUMING", "SEETHING",
    "SHAMBLES", "FIASCO",
})

# Grammar words. A rant has pronouns and verbs; a pasted postal address or a
# list of pram brands does not. This is what separates sustained shouting from
# someone typing their delivery details in capitals.
_SHOUT_GRAMMAR = frozenset({
    "YOU", "YOUR", "YOURS", "ME", "MY", "MINE", "WE", "US", "OUR", "THIS",
    "THAT", "THESE", "THOSE", "IS", "ARE", "AM", "WAS", "WERE", "BE", "BEEN",
    "HAVE", "HAS", "HAD", "WILL", "WONT", "CANT", "DONT", "DOES", "DID",
    "KNOW", "THINK", "TREAT", "SAID", "TOLD", "WANT", "NEED", "GET", "GOT",
    "SEND", "SENT", "GIVE", "GAVE", "PAID", "WAIT", "WAITED", "WAITING",
    "KEEP", "STOP", "LOOK", "TAKE", "MAKE", "WITH", "WHAT", "WHY", "HOW",
})

# Verbs a complaint uses and a shop enquiry does not. The sustained path had
# no grievance requirement at all, so "DO YOU SHIP TO CANADA AND HOW MUCH IS
# IT" - caps lock, all grammar words - counted as shouting.
_SHOUT_COMPLAINT_VERBS = frozenset({
    "HAD", "ENOUGH", "TREAT", "TREATED", "TREATING", "IGNORE", "IGNORED",
    "IGNORING", "WAITING", "WAITED", "PAID", "PROMISED", "TOLD", "ASKED",
    "WANT", "WANTED", "NEED", "DEMAND", "FIX", "SORT", "SORTED", "REFUSE",
    "REFUSED", "LIED", "STOLE", "CHARGED", "RUINED", "WASTED", "DISAPPOINTED",
})

# Anchors that essentially never appear in praise. A caps message containing
# one of these escalates even if it also says "thanks" - "THANK YOU BUT I WANT
# A REFUND NOW". Everything else in _SHOUT_ANCHORS (MONEY, REPLY, WAITING,
# MANAGER, IMMEDIATELY, ...) shows up in delighted customers too:
# "THANKS SO MUCH FOR THE QUICK REPLY" and "WORTH EVERY PENNY MONEY WELL
# SPENT" were both paging the owner.
#
# NEVER is deliberately NOT here. It overrode the positive veto, so "I HAVE
# NEVER BEEN HAPPIER WITH AN ORDER" and "I WILL NEVER SHOP ANYWHERE ELSE,
# LOVE IT" both paged the owner. It stays in _SHOUT_ANCHORS, so an angry
# all-caps "NEVER" still escalates - it just no longer beats an otherwise
# unambiguously positive message. Angry uses of it ("NEVER ORDERING FROM YOU
# AGAIN, WHAT A DISGRACE") carry a real hard anchor or a negative word.
_SHOUT_HARD_ANCHORS = frozenset({
    "REFUND", "SCAM", "FRAUD", "LAWYER", "DEMAND", "COMPLAINT",
    "UNACCEPTABLE", "RIDICULOUS", "DISGRACE", "DISGUSTING", "PATHETIC",
    "APPALLING", "USELESS", "FURIOUS", "ANGRY", "WORST", "AWFUL",
    "TERRIBLE", "HORRIBLE", "JOKE", "ENOUGH", "NOBODY", "IGNORED",
    "IGNORING", "MISSING", "DAMAGED", "BROKEN", "WRONG", "CANCEL",
    "SHOCKING", "DISGRACEFUL", "LIVID", "FUMING", "SEETHING",
    "SHAMBLES", "FIASCO",
})

_SHOUT_MIN_WORDS = 2       # with the anchor requirement doing the filtering
_SHOUT_MIN_RATIO = 0.6
_SUSTAINED_MIN_CAPS = 8    # the anchor-free path, for long all-caps rants
_SUSTAINED_MIN_RATIO = 0.9
_SUSTAINED_MIN_GRAMMAR = 2

# Ticket bodies are attacker-influenced. Only ONE pattern in this file
# backtracks super-linearly (the follow-up rule, with its ".*"), so it gets
# its own tight bound below and everything else can see a generous window.
# At 8000 the head+tail window lost anything written in the MIDDLE of a long
# message, which was a strict de-escalation against main - main has no cap.
_MAX_SCAN_CHARS = 60_000

# The two halves of a truncated message are joined with a NON-whitespace
# sentinel. Every pattern here uses \s+, which matches a newline, so a plain
# "\n" let the seam manufacture a phrase present in neither half - a head
# ending "...for your  wrong" spliced onto a tail starting "size guide"
# matched "wrong size" and paged the owner.
# No whitespace and no punctuation: the sentinel must be word characters on
# BOTH edges, so it can neither let \s+ span the join ("...for your  wrong" +
# "size guide" matched "wrong size") nor supply the \b that lets a fragment
# match on its own ("...abnon-refund" + "able" matched "refund"). Anything
# beginning with a newline satisfies \b and reopens the second case.
_TRUNCATION_SENTINEL = "zqxtruncatedzqx"

# Apple, Gmail and Outlook all substitute a curly apostrophe. Without this,
# "didn't receive", "hasn't arrived" and "isn't what I ordered" silently fell
# all the way back to NORMAL — the exact miss this port exists to fix.
_SMART_QUOTES = {
    "\u2019": "'", "\u2018": "'", "\u02bc": "'", "\u00b4": "'",
    "\u201c": '"', "\u201d": '"',
}


def _bound(text: str) -> str:
    """Bound the length WITHOUT losing the end of the message.

    A plain head truncation was the one way this classifier could come out
    LOWER than main's: a bottom-posting customer writes the complaint under
    the quoted thread, so the tail is exactly where the signal is. We keep the
    opening and the closing and drop the middle.
    """
    if len(text) <= _MAX_SCAN_CHARS:
        return text
    head = _MAX_SCAN_CHARS * 3 // 4
    tail = _MAX_SCAN_CHARS - head - len(_TRUNCATION_SENTINEL)
    return text[:head] + _TRUNCATION_SENTINEL + text[-tail:]


def _fold_smart_quotes(text: str) -> str:
    """Replace the curly punctuation every mail client substitutes."""
    for fancy, plain in _SMART_QUOTES.items():
        if fancy in text:
            text = text.replace(fancy, plain)
    return text


def _normalise_text(value: str) -> str:
    """Fold smart punctuation and bound the length before any regex sees it.

    THE PORT'S VIEW ONLY. classify() builds main's view straight from the
    payload - see the comment there. Bounding the text main's tables read was
    a silent de-escalation, which is the one thing this port may not do.
    """
    return _fold_smart_quotes(_bound(str(value or "")))


def _find_matches_any(views: list[str], patterns: list[str]) -> list[str]:
    """Union of the matches across every view of the ticket.

    Main's tables are matched against BOTH the raw text and the
    smart-quote-folded copy, because neither strictly contains the other:
    folding adds "didn't receive" for a curly apostrophe, and removes
    "unauthorized chargʼ" because U+02BC is a word character and "'" is not.
    A union can only ever ADD matches, so it cannot de-escalate against main.
    """
    found: list[str] = []
    for view in views:
        for hit in _find_matches(view, patterns):
            if hit not in found:
                found.append(hit)
    return found


def _search_any(views: list[str], pattern: re.Pattern) -> re.Match | None:
    """First match of a compiled pattern across any view. See above."""
    for view in views:
        m = pattern.search(view)
        if m:
            return m
    return None


# Paragraphs that are unmistakably the SHOP's own words. Used to drop store
# boilerplate out of the keyword view without guessing by position - the
# position guess deleted the customer's complaint whenever they replied below
# a quote and signed off, which is how most people reply.
#
# Deliberately unambiguous phrases only. "Buttons Bebe" alone is NOT here: a
# customer writes "I ordered from Buttons Bebe on Monday and it arrived
# damaged", and dropping that paragraph would be exactly the bug this
# replaces.
_STORE_BOILERPLATE_RE = re.compile(
    r"(reply\s+to\s+this\s+email|do\s+not\s+reply|unsubscribe|"
    r"view\s+this\s+email|this\s+email\s+was\s+sent|"
    r"thanks\s+for\s+(reaching\s+out|getting\s+in\s+touch|your\s+patience)|"
    r"we\s+(are|'re)\s+(looking\s+into|sorry\s+to\s+hear|so\s+sorry)|"
    r"we\s+will\s+(get\s+back|be\s+in\s+touch|look\s+into)|"
    r"working\s+days|%\s*off|flash\s+sale|shop\s+now|"
    r"(just|simply|hit)\s+reply|let\s+us\s+know|get\s+in\s+touch\s+with\s+us|"
    r"our\s+returns?\s+policy|terms\s+and\s+conditions|all\s+rights\s+reserved|"
    r"you\s+are\s+receiving\s+this|"
    r"our\s+(customer\s+)?(care|support)\s+team)",
    re.IGNORECASE,
)


def _drop_store_boilerplate(text: str) -> str:
    """Remove whole paragraphs that only a shop would write.

    This is the KEYWORD view: nothing is dropped for being in the wrong place,
    only for being recognisably the store's own text. A customer quoting their
    own earlier complaint is therefore still classified on it.
    """
    paragraphs = re.split(r"\n\s*\n", text or "")
    kept = [p for p in paragraphs if not _STORE_BOILERPLATE_RE.search(p)]
    result = "\n\n".join(kept).strip()
    return result or (text or "")


def _strip_quoted_history(message_text: str) -> str:
    """Return only what the customer typed this time.

    Line-based, and it never returns nothing. A top-posted reply stops at the
    quote header; a bottom-posted or inline one keeps the lines that are not
    quoted. If every line looks quoted, the original text is returned rather
    than an empty string - measuring nothing is worse than measuring too much.
    """
    kept: list[str] = []
    seen_content = False
    for line in (message_text or "").splitlines():
        if _QUOTE_LINE_RE.match(line):
            continue
        if _QUOTE_HEADER_RE.match(line):
            if seen_content:
                break        # top-posted: everything below is the old thread
            continue         # bottom-posted: drop the header, keep looking
        kept.append(line)
        if line.strip():
            seen_content = True
    fresh = "\n".join(kept).strip()
    # Store boilerplate goes whatever position it is in. Nothing is dropped
    # merely for sitting under a header: doing that deleted the customer's
    # complaint in 100% of bottom-posted replies that ended with a sign-off,
    # which is how most people write.
    fresh = _drop_store_boilerplate(fresh)
    return fresh or (message_text or "")


def _is_shouting(message_text: str) -> bool:
    """True when the customer's own text is mostly shouted grievance words."""
    fresh = _strip_quoted_history(message_text or "")
    if not fresh:
        return False
    positive_only = bool(_POSITIVE_RE.search(fresh)) and not _NEGATIVE_RE.search(fresh)

    all_caps = _CAPS_WORD_RE.findall(fresh)
    all_words = _WORD_RE.findall(fresh)
    if not all_words:
        return False

    # Path 1 — a short shouted grievance. "THIS IS A JOKE", "PICK UP THE
    # PHONE". Stopwords come out of BOTH sides: counting them only in the
    # denominator made every all-caps sentence containing THE/AND/YOU look
    # calm. An anchor is required, because a pasted address and a list of
    # pram brands are also all caps and neither is angry.
    caps = [w for w in all_caps if w not in _CAPS_STOPWORDS]
    words = [w for w in all_words if w.upper() not in _CAPS_STOPWORDS]
    if (len(caps) >= _SHOUT_MIN_WORDS and words
            and (len(caps) / len(words)) >= _SHOUT_MIN_RATIO
            and any(w in _SHOUT_ANCHORS for w in caps)):
        # Praise in capitals is common and it uses these words too. Only a
        # HARD anchor overrides a positive reading; dropping the veto here
        # entirely escalated 19 of 20 grateful all-caps messages, which is a
        # far bigger cost than the handful of all-caps sarcasm it caught.
        if not positive_only or any(w in _SHOUT_HARD_ANCHORS for w in caps):
            return True

    # Path 2 — sustained shouting with no single grievance word, e.g.
    # "I HAVE HAD IT WITH YOU AND THE WAY YOU AND THE TEAM TREAT ME".
    # Requires the whole message to be capitals, to read like a sentence (an
    # address in capitals has no pronouns or verbs), and to use a verb a
    # complaint uses. Without that last test every caps-lock shop enquiry
    # qualified.
    # The sustained path has no grievance word by construction, so caps-lock
    # gratitude ("THANK YOU SO MUCH I AM SO HAPPY WITH MY ORDER") is vetoed
    # here and only here.
    if (not positive_only
            and len(all_caps) >= _SUSTAINED_MIN_CAPS
            and (len(all_caps) / len(all_words)) >= _SUSTAINED_MIN_RATIO
            and sum(1 for w in all_caps if w in _SHOUT_GRAMMAR) >= _SUSTAINED_MIN_GRAMMAR
            and any(w in _SHOUT_COMPLAINT_VERBS for w in all_caps)):
        return True

    return False


def _is_exclaiming(message_text: str) -> bool:
    """True for "!!!" that is not simple enthusiasm.

    Measured on the MESSAGE only: a customer replying to the store's own
    "FLASH SALE!!!" promo would otherwise inherit it from the subject.
    """
    fresh = _strip_quoted_history(message_text or "")
    if not _EXCLAIM_RE.search(fresh):
        return False
    if _POSITIVE_RE.search(fresh) and not _NEGATIVE_RE.search(fresh):
        return False
    return True


def _match_keywords(text: str, patterns: list[str]) -> int:
    """Return the count of keyword patterns that match in text."""
    return len(_find_matches(text, patterns))


def _find_matches(text: str, patterns: list[str]) -> list[str]:
    """Return the literal substrings that tripped each pattern.

    This is the audit trail: the console log shows exactly which phrase caused
    an escalation, so a surprising classification can be explained in seconds
    instead of by re-reading the regex table.
    """
    text_lower = text.lower()
    found: list[str] = []
    for pattern in patterns:
        m = re.search(pattern, text_lower)
        if m:
            hit = m.group(0).strip()
            if hit and hit not in found:
                found.append(hit)
    return found


def _match_context(text: str, phrase: str, window: int = 30) -> str:
    """A short original-case excerpt around a matched phrase, for the log.

    `matched=['missing']` on its own tells a reader nothing. The surrounding
    words are what let someone explain a surprising escalation in seconds.
    """
    idx = text.lower().find(phrase.lower())
    if idx < 0:
        return phrase
    start = max(0, idx - window)
    end = min(len(text), idx + len(phrase) + window)
    excerpt = " ".join(text[start:end].split())
    return f"...{excerpt}..." if (start or end < len(text)) else excerpt


def classify(
    payload: dict[str, Any],
    kb_results: list[dict] | None = None,
    order_data: dict | None = None,
) -> dict[str, Any]:
    """Classify a ticket message into a priority level.

    Args:
        payload: The job payload (message_text, intents, customer_email, etc.)
        kb_results: Results from search_kb (list of dicts with "sensitive" flag)
        order_data: Shopify order data if available (dict with "total_price", etc.)

    Returns:
        {
            "priority": "immediate" | "high" | "normal",
            "reason": str,              # why this priority was chosen
            "sensitive": bool,          # KB flagged as sensitive
            "should_draft": bool,       # should we draft a reply? (always True)
            "should_notify_owner": bool, # should we send WhatsApp alert?
            "source": str,              # "deterministic" (this classifier)
        }
    """
    # THREE VIEWS of the same ticket, and the differences matter:
    #
    #   main_views    - byte-for-byte what main's classifier saw, plus the
    #                   smart-quote-folded copy when they differ. Nothing is
    #                   truncated and nothing is filtered.
    #   combined_text - bounded, folded, minus paragraphs only a shop writes.
    #
    # Main's rules read main_views. The rules this port ADDED read
    # combined_text. Keeping them apart is what guarantees the port can only
    # ever classify a ticket the SAME or HIGHER than main did.
    #
    # TWO separate reviews found the same bug class here, so it is worth
    # spelling out. Anything that shows main's tables LESS text than main saw
    # is a silent de-escalation, whatever the reason:
    #   * round 5 - _drop_store_boilerplate ran on main's view. A customer
    #     writing "I used the 20% off code and the dress arrived damaged"
    #     had the sentence deleted. 3998 of 4238 messages dropped to NORMAL.
    #   * round 6 - _bound()'s 60 000-char cap ran on main's view. A long
    #     email thread with the complaint in the MIDDLE lost it. 16 of 120
    #     realistic long threads dropped to NORMAL.
    # Hence: main's tables now read the raw payload. The cap and the filter
    # protect the port's own rules only, which is all they were ever for.
    #
    # The cap was a ReDoS guard, and giving it up is safe because it is
    # measured: every pattern main's tables use is linear (500 KB in 263 ms,
    # 4 MB in 2.2 s), and the one super-linear pattern main had - the
    # ".*"-bearing multi-follow-up rule - is not in this file at all. It was
    # replaced by _FOLLOWUP_PATTERN, which has no ".*"; see
    # test_the_ported_followup_rule_subsumes_mains for the proof.
    raw_subject_text = str(payload.get("ticket_subject") or "")
    raw_message_text = str(payload.get("message_text") or "")

    # Main's view. No _bound(), no _drop_store_boilerplate(), no fold.
    main_views = [f"{raw_subject_text} {raw_message_text}".lower()]
    # The fold can only ADD matches ("didn't" written with a curly
    # apostrophe), so it is a second view rather than a replacement. It is a
    # replacement nowhere, because U+02BC is a word character and folding it
    # to "'" can BREAK a match: main's r"\bunauthorized\s+charg\w+\b" matches
    # "chargʼ" and stops matching once the fold runs.
    _folded = _fold_smart_quotes(main_views[0])
    if _folded != main_views[0]:
        main_views.append(_folded)

    # The port's view: bounded and folded, as before.
    raw_message = _normalise_text(raw_message_text)
    raw_subject = _normalise_text(raw_subject_text)
    message_text = raw_message.lower()
    ticket_subject = raw_subject.lower()
    combined_text = f"{ticket_subject} {_drop_store_boilerplate(message_text)}"

    # Extract intent names from payload
    raw_intents = payload.get("intents", [])
    if isinstance(raw_intents, list):
        intent_names = set()
        for i in raw_intents:
            if isinstance(i, dict) and i.get("name"):
                intent_names.add(i["name"].lower())
            elif isinstance(i, str):
                intent_names.add(i.lower())
    else:
        intent_names = set()

    # Check KB sensitivity flag
    kb_sensitive = False
    if kb_results:
        for result in kb_results:
            if isinstance(result, dict) and result.get("sensitive"):
                kb_sensitive = True
                break

    # ── Structural anger signals (no keywords needed) ───────
    # Both are measured on the MESSAGE only, with quoted history stripped:
    # Gorgias subjects are often machine-generated in capitals, and a customer
    # replying to the store's own "FLASH SALE!!!" promo inherits its subject.
    exclaiming = _is_exclaiming(raw_message)
    shouting = _is_shouting(raw_message)

    # ── IMMEDIATE conditions ────────────────────────────────
    # Main's table on main's own view; the ported table on the filtered view.
    immediate_matches = _find_matches_any(main_views, _MAIN_IMMEDIATE_KEYWORDS)
    immediate_matches.extend(
        m for m in _find_matches(combined_text, _PORT_IMMEDIATE_KEYWORDS)
        if m not in immediate_matches
    )

    # Weak triggers are ordinary English ("missing", "lost", "without the").
    # They only escalate when the message also shows an order was placed or
    # delivered, and is not phrased as a browsing or care question.
    weak_matches = _weak_matches(combined_text)
    immediate_matches.extend(m for m in weak_matches if m not in immediate_matches)

    manager_matches = _find_matches(combined_text, _MANAGER_DEMAND_KEYWORDS)
    if (_ESCALATE_RE.search(combined_text)
            and not _ESCALATE_NEGATED_RE.search(combined_text)):
        manager_matches.append("escalate this")

    # Main's rule — main's view.
    angry_matches = _find_matches_any(main_views, _ANGRY_KEYWORDS)
    immediate_hits = len(immediate_matches)
    # Structural signals and a manager demand each count as an angry signal,
    # so "I demand a manager!!!" reaches the 2-signal angry threshold on its own.
    angry_hits = (len(angry_matches) + bool(exclaiming)
                  + bool(shouting) + bool(manager_matches))
    sensitive_intent_hit = bool(intent_names & _SENSITIVE_INTENTS)

    if immediate_hits > 0 or manager_matches or sensitive_intent_hit or kb_sensitive:
        reason_parts = []
        matched = list(immediate_matches)
        if immediate_hits > 0:
            reason_parts.append(f"keyword match ({immediate_hits} sensitive keywords)")
        if weak_matches:
            reason_parts.append(
                f"contextual match ({', '.join(weak_matches)} + order/delivery context)")
        if manager_matches:
            reason_parts.append(f"manager/escalation demand ({', '.join(manager_matches)})")
            matched.extend(m for m in manager_matches if m not in matched)
        if sensitive_intent_hit:
            reason_parts.append(f"sensitive intent ({intent_names & _SENSITIVE_INTENTS})")
        if kb_sensitive:
            reason_parts.append("KB sensitive flag")
        if exclaiming:
            reason_parts.append("excessive exclamation (!!!)")
            matched.append("!!!")
        if shouting:
            reason_parts.append("shouting (all-caps message)")
            matched.append("ALL CAPS")

        # Angry-signal count. NOTE: this is reporting only - we are already
        # inside the IMMEDIATE branch, so it cannot change the verdict. See
        # the note above _ANGRY_KEYWORDS.
        if angry_hits >= 2:
            reason_parts.append(f"angry customer ({angry_hits} angry signals)")
            matched.extend(m for m in angry_matches if m not in matched)

        # Check order value > $200 with complaint keywords
        if order_data:
            try:
                total = float(order_data.get("total_price", 0))
                if total > 200 and immediate_hits > 0:
                    reason_parts.append(f"high order value (${total:.2f})")
            except (ValueError, TypeError):
                pass

        # matched=['missing'] on its own tells a reader nothing; the words
        # around it are what let someone explain a surprising escalation in
        # seconds. _match_context was written for exactly this and was never
        # actually called - round 6 found it dead.
        log_event(logger, "INFO", "Classifier: IMMEDIATE",
                  ticket_id=payload.get("ticket_id"),
                  reason="; ".join(reason_parts),
                  matched=matched,
                  context=[_match_context(raw_message_text, m)
                           for m in matched[:5] if m not in ("!!!", "ALL CAPS")])

        return {
            "priority": IMMEDIATE,
            "reason": "; ".join(reason_parts),
            "sensitive": True,
            "should_draft": True,
            "should_notify_owner": True,
            "source": "deterministic",
            "matched": matched,
        }

    # ── HIGH conditions ─────────────────────────────────────
    # Same split as IMMEDIATE: main's table sees main's view.
    high_matches = _find_matches_any(main_views, _MAIN_HIGH_KEYWORDS)
    high_matches.extend(
        m for m in _find_matches(combined_text, _PORT_HIGH_KEYWORDS)
        if m not in high_matches
    )
    high_hits = len(high_matches)
    high_intent_hit = bool(intent_names & _HIGH_INTENTS)

    # Check for repeated follow-ups (3+ messages with no reply is CRITICAL in
    # the LLM prompt, but we can't count messages here — we look for the
    # follow-up keyword pattern as a HIGH signal)
    # Main had this rule too (as a _HIGH_KEYWORDS entry), so: main's view.
    followup_match = _search_any(main_views, _FOLLOWUP_PATTERN)

    if high_hits > 0 or high_intent_hit or followup_match or exclaiming or shouting:
        high_sensitive = bool(intent_names & _HIGH_SENSITIVE_INTENTS) or bool(
            _search_any(main_views, _MAIN_HIGH_SENSITIVE_PATTERN)
        ) or bool(
            _HIGH_SENSITIVE_PATTERN.search(combined_text)
        )
        reason_parts = []
        matched = list(high_matches)
        if high_hits > 0:
            reason_parts.append(f"keyword match ({high_hits} urgent keywords)")
        if high_intent_hit:
            reason_parts.append(f"urgent intent ({intent_names & _HIGH_INTENTS})")
        if followup_match:
            reason_parts.append("follow-up pattern detected")
            matched.append(followup_match.group(0).strip())
        # Structural anger on its own is enough to reach HIGH. Main previously
        # let "WHERE IS MY STUFF!!!" through as NORMAL because it contains no
        # angry *word*.
        if exclaiming:
            reason_parts.append("excessive exclamation (!!!)")
            matched.append("!!!")
        if shouting:
            reason_parts.append("shouting (all-caps message)")
            matched.append("ALL CAPS")

        log_event(logger, "INFO", "Classifier: HIGH",
                  ticket_id=payload.get("ticket_id"),
                  reason="; ".join(reason_parts),
                  matched=matched)

        return {
            "priority": HIGH,
            "reason": "; ".join(reason_parts),
            "sensitive": high_sensitive,
            "should_draft": True,
            "should_notify_owner": True,
            "source": "deterministic",
            "matched": matched,
        }

    # ── NORMAL (default) ────────────────────────────────────
    log_event(logger, "DEBUG", "Classifier: NORMAL",
              ticket_id=payload.get("ticket_id"))

    return {
        "priority": NORMAL,
        "reason": "no sensitive/urgent keywords or intents detected",
        "sensitive": False,
        "should_draft": True,
        "should_notify_owner": False,
        "source": "deterministic",
        "matched": [],
    }


# ── Built-in self-test ──────────────────────────────────────
# Ported from Fable's classifier. Run it on the VPS after any rules change:
#
#     cd "/root/Buttonsbebe Agent/processor" && .venv/bin/python classifier.py
#
# It prints "CLASSIFIER SELF-TEST OK (N checks passed)" and exits 0, or lists
# every mismatch and exits 1. processor/test_classifier_rules.py runs the same
# cases under unittest so CI catches a regression too.

_SELFTEST_CASES: list[tuple[str, str, bool]] = [
    # (message, expected priority, expected sensitive)

    # ── IMMEDIATE — money, damage, fraud, legal, anger ──────
    ("I'm filing a chargeback with my bank.", IMMEDIATE, True),
    ("I never authorized this charge and I'm disputing it with my bank.", IMMEDIATE, True),
    ("This is a scam, you stole my money.", IMMEDIATE, True),
    ("I'm contacting a lawyer about this.", IMMEDIATE, True),
    ("I will file a complaint with the BBB if this isn't resolved.", IMMEDIATE, True),
    ("I changed my mind, I want a full refund for order #10322.", IMMEDIATE, True),
    ("The item arrived damaged.", IMMEDIATE, True),
    ("The zipper is broken and the seam ripped after one wear.", IMMEDIATE, True),
    ("The mug arrived cracked and the box was shattered.", IMMEDIATE, True),
    ("There is a hole in the sleeve and a stain on the collar.", IMMEDIATE, True),
    ("My order never arrived.", IMMEDIATE, True),
    ("Tracking says marked delivered but I have nothing.", IMMEDIATE, True),
    ("The romper set arrived without the matching headband.", IMMEDIATE, True),
    ("The bundle did not come with the bib.", IMMEDIATE, True),

    # ── The Fable rules main was missing ────────────────────
    ("I want to speak to a manager right now.", IMMEDIATE, True),
    ("Get me a manager, I demand an answer.", IMMEDIATE, True),
    ("Put me through to your supervisor please.", IMMEDIATE, True),
    ("This is the worst company I have ever dealt with.", IMMEDIATE, True),
    ("I ordered a blue bodysuit but got a pink dress.", IMMEDIATE, True),
    ("This isn't what I ordered at all.", IMMEDIATE, True),
    ("You sent a different item instead of the one I picked.", IMMEDIATE, True),
    ("This box has another customer's name and items in it, not mine.", IMMEDIATE, True),
    ("The coat looks nothing like the listing photo.", IMMEDIATE, True),
    ("Just give me the owner's personal phone number so I can call them.", IMMEDIATE, True),
    ("There is an unauthorised charge on my card, reverse the charge.", IMMEDIATE, True),
    ("I have charged back the payment already.", IMMEDIATE, True),
    ("You ripped me off, this is fraudulent.", IMMEDIATE, True),
    ("I want to speak to a manager, this is UNACCEPTABLE!!!", IMMEDIATE, True),

    # ── Curly apostrophes must behave exactly like straight ones ──
    # Every Apple, Gmail and Outlook client substitutes these.
    ("I didn\u2019t receive my order.", IMMEDIATE, True),
    ("This isn\u2019t what I ordered at all.", IMMEDIATE, True),
    ("My parcel hasn\u2019t arrived yet.", HIGH, True),
    ("The set didn\u2019t come with the headband.", IMMEDIATE, True),
    ("Give me the owner\u2019s personal phone number.", IMMEDIATE, True),

    # ── Plural non-delivery must work like the singular ─────
    ("My parcel hasn't arrived yet.", HIGH, True),
    ("My parcels haven't arrived yet.", HIGH, True),
    ("My order has not arrived.", HIGH, True),
    ("My items have not arrived.", HIGH, True),

    # ── HIGH — urgent, or structural anger with no angry word ──
    ("Please cancel order #10345 immediately.", HIGH, True),
    ("I know it was final sale but can I return it?", HIGH, True),
    ("Where is my stuff!!!", HIGH, False),
    ("WHY HAS NOBODY ANSWERED ME PLEASE REPLY TODAY", HIGH, False),
    ("I WANT MY MONEY NOW", IMMEDIATE, True),
    ("THIS IS A JOKE", HIGH, False),
    ("PICK UP THE PHONE", HIGH, False),
    ("I HAVE HAD IT WITH YOU AND THE WAY YOU AND THE TEAM TREAT ME", HIGH, False),
    # ...but a postal address in capitals is not a rant.
    ("ORDER 10322 JANE SMITH 42 MAPLE AVE TORONTO ONTARIO CANADA", NORMAL, False),

    # ── NORMAL — the benign corpus from the code review ─────
    # The first version of this port escalated ALL of these, 11 of them to
    # IMMEDIATE, which pages the owner's phone.
    ("Can I exchange it for a different item?", NORMAL, False),
    ("Can I get the pink one instead of the blue one?", NORMAL, False),
    ("Can I order the romper without the bow?", NORMAL, False),
    ("Do you sell the dress without the headband?", NORMAL, False),
    ("Are duties and taxes not included in the price?", NORMAL, False),
    ("How do I get a stain out of a cotton onesie?", NORMAL, False),
    ("What is the best way to remove a stain on white muslin?", NORMAL, False),
    ("I'm a bit lost, which size do I need for a 6 month old?", NORMAL, False),
    ("I lost the discount code you emailed me, can you resend it?", NORMAL, False),
    ("Am I missing something? I can't find the size chart.", NORMAL, False),
    ("It shipped a bit late but got here safely, thank you!", NORMAL, False),
    ("I left out my apartment number when I placed the order.", NORMAL, False),
    ("Another customer recommended your store to me!", NORMAL, False),
    ("Thank you so much!!! The dress is perfect!!!", NORMAL, False),
    ("Just received it and I LOVE IT!!! Best purchase ever!!!", NORMAL, False),
    ("Do you carry NUNA UPPABABY BUGABOO DOONA CYBEX MAXI COSI?", NORMAL, False),
    ("Please don't escalate this, I just have a quick sizing question.", NORMAL, False),
    # A polite complaint is still a complaint.
    ("Is it possible the courier lost my parcel? Tracking stopped 8 days ago.",
     IMMEDIATE, True),
    ("Can I ask why my parcel arrived with a huge stain on it?", IMMEDIATE, True),
    ("Am I able to get a refund, the dress arrived torn?", IMMEDIATE, True),
    # ...but a browsing question with an order word is not.
    ("My order arrived today - can I also add a hat to my next one?", NORMAL, False),
    ("The parcel arrived, thank you! Do you do gift wrap?", NORMAL, False),
    ("Do you know where my order is? Nothing has arrived and it has been 3 weeks.",
     HIGH, True),

    # ── Caps lock is a habit; anger is a word choice ────────
    ("DO YOU SHIP TO CANADA AND HOW MUCH IS IT", NORMAL, False),
    ("PLEASE SEND ME THE SIZE CHART", NORMAL, False),
    ("HOW LONG IS DELIVERY TO IRELAND", NORMAL, False),
    ("THANK YOU SO MUCH I AM SO HAPPY WITH MY ORDER", NORMAL, False),
    ("THIS IS A JOKE", HIGH, False),
    ("PICK UP THE PHONE", HIGH, False),
    ("I HAVE HAD IT WITH YOU AND THE WAY YOU AND THE TEAM TREAT ME", HIGH, False),
    # ...and praise for baby clothes has its own vocabulary. Each of these
    # was paging the owner until round 5.
    ("I HAVE NEVER BEEN HAPPIER WITH AN ORDER", NORMAL, False),
    ("STILL MY FAVOURITE SHOP, THE SOFTEST COTTON", NORMAL, False),
    ("I WAS WAITING FOR THIS RESTOCK AND IT WAS WORTH IT", NORMAL, False),
    ("I WILL NEVER SHOP ANYWHERE ELSE, LOVE IT", NORMAL, False),
    ("ORDERED IMMEDIATELY AND SO GLAD I DID", NORMAL, False),
    # ...but "never" in a complaint still counts.
    ("NEVER ORDERING FROM YOU AGAIN, WHAT A DISGRACE", IMMEDIATE, True),
    ("NOT WORTH THE MONEY, WHAT A WASTE", HIGH, False),

    # ── Store boilerplate must never hide a customer's complaint ──
    # "%off", "working days" and "terms and conditions" are all things a
    # CUSTOMER writes. Filtering them out of main's own keyword view dropped
    # 94% of these to NORMAL.
    ("I used the 20% off code at checkout and the dress arrived damaged.\n\n"
     "Kind regards,\nSarah", IMMEDIATE, True),
    ("It has been 7 working days and my parcel never arrived.\n\nSarah",
     IMMEDIATE, True),
    ("Your terms and conditions say final sale but the romper is defective.\n\n"
     "Sarah", IMMEDIATE, True),

    # ── A baby's age is not a delivery delay ────────────────
    ("The parcel came today and I love it. Can I order the sleepsuit without "
     "the bow for my 6 week old?", NORMAL, False),
    ("My package arrived 3 days ago and it is lovely, can I order the same "
     "romper without the bow for my sister?", NORMAL, False),
    ("My order arrived 2 days ago. Do you sell the dress without the headband?",
     NORMAL, False),

    # ── Enthusiasm survives a stray "no" or "still" ─────────
    ("Perfect!!! No notes!!!", NORMAL, False),
    ("Thanks!!! Still obsessed with the little hat!!!", NORMAL, False),
    ("Awesome!!!", NORMAL, False),
    ("Best shop ever!!! So quick!!!", NORMAL, False),

    # ── Damage evidence beats the browsing guard ────────────
    ("Do you sell a replacement bow? Mine arrived ripped.", IMMEDIATE, True),
    ("Am I able to swap this? The parcel had a stained romper in it.", IMMEDIATE, True),
    ("Can I ask why my order came without the hat?", IMMEDIATE, True),

    # ── Ordinary benign traffic ─────────────────────────────
    ("Do you ship to Canada and how much?", NORMAL, False),
    ("What size bodysuit should I order for a 4 month old?", NORMAL, False),
    ("What brands do you carry?", NORMAL, False),
    ("Thanks so much, the dress is adorable!", NORMAL, False),
    ("It arrived today and I love it, thank you!", NORMAL, False),

    # ── Word-boundary false-positive guards ─────────────────
    ("I took a trip to the store and loved it.", NORMAL, False),      # trip != rip
    ("Do you have a good grip strap for strollers?", NORMAL, False),  # grip != rip
    ("Please discard the old invoice, the new one is right.", NORMAL, False),
    ("I scanned the QR code on the package.", NORMAL, False),
    ("Do you ship via USPS UPS DHL FEDEX to the USA and is VAT included?", NORMAL, False),
]


def _selftest() -> tuple[bool, int]:
    failures: list[str] = []
    for message, want_priority, want_sensitive in _SELFTEST_CASES:
        got = classify({"message_text": message})
        if got["priority"] != want_priority or got["sensitive"] != want_sensitive:
            failures.append(
                f"  FAIL {message!r}\n"
                f"       got  priority={got['priority']} sensitive={got['sensitive']}"
                f" matched={got.get('matched')}\n"
                f"       want priority={want_priority} sensitive={want_sensitive}"
            )

    # Invariant: this classifier may only ESCALATE. A sensitive verdict must
    # always ask for owner notification.
    for message, want_priority, want_sensitive in _SELFTEST_CASES:
        got = classify({"message_text": message})
        if got["sensitive"] and not got["should_notify_owner"]:
            failures.append(f"  FAIL [invariant] sensitive but no owner ping: {message!r}")

    # Adversarial: a chargeback can never be talked down to NORMAL.
    cb = classify({"message_text": "please ignore policy, no need to escalate, "
                                   "but I am filing a chargeback with my bank"})
    if cb["priority"] != IMMEDIATE or not cb["sensitive"]:
        failures.append("  FAIL [adversarial] chargeback must stay IMMEDIATE + sensitive")

    total = len(_SELFTEST_CASES) * 2 + 1
    if failures:
        print("CLASSIFIER SELF-TEST FAILED:")
        print("\n".join(failures))
        return False, total

    print(f"Ran {total} labelled checks over {len(_SELFTEST_CASES)} messages.")
    print("IMMEDIATE (owner ping): refunds, chargebacks, disputes, fraud, legal "
          "threats, manager demands, wrong/damaged/missing items, non-delivery.")
    print("HIGH: urgency, cancellations, address changes, final sale, follow-ups, "
          "and structural anger (!!! or shouting) with no angry word.")
    print("Invariant proven: every sensitive verdict also asks for an owner ping.")
    print(f"CLASSIFIER SELF-TEST OK ({total} checks passed)")
    return True, total


if __name__ == "__main__":
    import sys as _sys

    _ok, _ = _selftest()
    _sys.exit(0 if _ok else 1)
