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
_IMMEDIATE_KEYWORDS = [
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

    # ── Ported from the Fable branch (rules only — Task 4 of the port).
    # Only phrases that are UNAMBIGUOUS in a support inbox go in this list;
    # the merely-suggestive ones live in _WEAK_IMMEDIATE below and need
    # corroborating context before they fire. See the note above that list.

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

    # Damage reported as a fact about a received item.
    r"\bcracked\b", r"\bshattered\b", r"\bfrayed\b", r"\bfell\s+apart\b",
    r"\bseam\s+ripped\b",
    # "has/have/had" alone are too weak here: "Do you have a tear-away label?"
    # is a product question, not a damage report. Require a reporting subject,
    # and never match the compound "tear-away".
    r"\b(?:there\s?'?s|there\s+is|it\s+has|it\s+had|came\s+with|"
    r"arrived\s+with|turned\s+up\s+with|found)\s+(?:a\s+)?(?:big\s+|small\s+|"
    r"large\s+|huge\s+|tiny\s+)?(?:hole|rip|tear|stain|snag)\b(?!\s*-?\s*away)",

    # Missing / undelivered, phrased unambiguously
    r"\b(?:did\s+not|didn'?t)\s+come\s+with\b",
    r"\bmarked\s+delivered\s+but\b",
]

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
_WEAK_IMMEDIATE = [
    r"\bmissing\b",
    r"\blost\b",
    r"\bwithout\s+the\b",
    r"\bnot\s+included\b", r"\bwas\s?n'?t\s+included\b",
    r"\bleft\s+out\b", r"\bsupposed\s+to\s+include\b",
    r"\bdifferent\s+item\b", r"\binstead\s+of\s+the\b",
    r"\bripped\b", r"\bstained\b",
    r"\ba\s+(?:hole|rip|tear|stain)\b(?!\s*-?\s*away)",
    r"\b(?:hole|rip|tear|stain)\s+(?:in|on)\b",
    r"\banother\s+customer\b",
    r"\bsomeone\s+else'?s?\s+(order|name|items?|package|parcel|box)\b",
]

# Evidence that this is about a real order, not a pre-sale question.
_ORDER_CONTEXT_RE = re.compile(
    r"\b("
    r"arrived|delivered|delivery|received|came\s+(?:in|today|yesterday)|"
    r"parcel|parcels|package|packages|shipment|the\s+box|my\s+box|in\s+the\s+box|"
    r"tracking|courier|dispatched|"
    r"my\s+(?:order|purchase|item|items|delivery|parcel|package)|"
    r"you\s+sent|sent\s+me|i\s+ordered|i\s+bought|i\s+purchased|"
    r"order\s*#?\s*\d|#\s*\d{3,}"
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


def _weak_triggers_apply(text: str) -> bool:
    """True when a weak trigger is allowed to escalate."""
    if _BROWSING_QUESTION_RE.search(text):
        return False
    return bool(_ORDER_CONTEXT_RE.search(text))


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
_HIGH_KEYWORDS = [
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
    # Multiple follow-ups
    r"\b(following\s+up|follow\s?up)\b.*(again|still|yet|no\s+(response|reply|answer))\b",

    # ── Ported from Fable (Task 4). Non-delivery phrasings main missed.
    # These sit at HIGH, not IMMEDIATE: "I still haven't received it" is the
    # single most common where-is-my-order wording, and routing every WISMO to
    # the owner's phone would bury the alerts that matter. Outright theft
    # signals ("never arrived", "marked delivered but") stay IMMEDIATE above.
    # Main covered only the singular "hasn't received"; the plural forms and
    # "hasn't arrived" fell all the way to NORMAL.
    r"\b(?:has\s?n'?t|has\s+not|have\s+not|have\s?n'?t)\s+(?:arrived|turned\s+up|shown\s+up)\b",
    r"\bstill\s+(?:has\s?n'?t|have\s?n'?t|not)\s+(?:arrived|come|received)\b",
    r"\bnot\s+(?:been\s+)?delivered\b",
]

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
    r"not\s+(?:been\s+)?delivered)\b",
    re.IGNORECASE,
)

# Angry indicator count threshold — if 2+ angry keywords, force IMMEDIATE
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
    r"\b(thank|thanks|thankyou|love|loved|loving|adorable|perfect|beautiful|"
    r"gorgeous|cute|amazing|wonderful|excellent|obsessed|delighted|thrilled|"
    r"pleased|happy|brilliant|fantastic|lovely)\b", re.IGNORECASE)
_NEGATIVE_RE = re.compile(
    r"\b(not|no|never|refund|damaged|broken|wrong|missing|late|angry|furious|"
    r"unacceptable|terrible|awful|worst|horrible|disappointed|disappointing|"
    r"ridiculous|useless|rubbish|scam|fraud|cancel|complaint|complain|waiting|"
    r"still|nobody|noone|ignore|ignored|refuse|refused)\b", re.IGNORECASE)

# Quoted email history dilutes every ratio, so measure the new text only.
_QUOTE_LINE_RE = re.compile(r"^\s*>", re.MULTILINE)
_QUOTE_HEADER_RE = re.compile(
    r"^\s*(?:on\s.{0,120}\swrote:|-{2,}\s*original message|_{5,}|from:\s)",
    re.IGNORECASE | re.MULTILINE)

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
_SHOUT_ANCHORS = frozenset({
    "WHY", "WHAT", "WHERE", "WHEN", "WHO", "HOW", "THIS", "THAT", "YOUR",
    "NEVER", "STILL", "PLEASE", "HELP", "WANT", "NEED", "MONEY", "REFUND",
    "NOW", "TODAY", "IMMEDIATELY", "UNACCEPTABLE", "RIDICULOUS", "AGAIN",
    "ANSWER", "ANSWERED", "REPLY", "RESPOND", "RESPONSE", "WAITING", "WRONG",
    "BROKEN", "DAMAGED", "MISSING", "CANCEL", "TERRIBLE", "AWFUL", "WORST",
    "JOKE", "SERIOUSLY", "ENOUGH", "DONE", "SICK", "TIRED", "FED", "PHONE",
    "CALL", "SPEAK", "MANAGER", "DEMAND", "LAST", "FINAL", "URGENT", "SCAM",
    "FRAUD", "LAWYER", "NOBODY", "USELESS", "APPALLING", "DISGRACE", "ANGRY",
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

_SHOUT_MIN_WORDS = 2       # with the anchor requirement doing the filtering
_SHOUT_MIN_RATIO = 0.6
_SUSTAINED_MIN_CAPS = 6    # the anchor-free path, for long all-caps rants
_SUSTAINED_MIN_RATIO = 0.9
_SUSTAINED_MIN_GRAMMAR = 2

# Ticket bodies are attacker-influenced and some pre-existing patterns in this
# file backtrack super-linearly. Classification only ever needs the opening of
# a message, so bound what the regexes ever see.
_MAX_SCAN_CHARS = 8000

# Apple, Gmail and Outlook all substitute a curly apostrophe. Without this,
# "didn't receive", "hasn't arrived" and "isn't what I ordered" silently fell
# all the way back to NORMAL — the exact miss this port exists to fix.
_SMART_QUOTES = {
    "\u2019": "'", "\u2018": "'", "\u02bc": "'", "\u00b4": "'",
    "\u201c": '"', "\u201d": '"',
}


def _normalise_text(value: str) -> str:
    """Fold smart punctuation and bound the length before any regex sees it."""
    text = str(value or "")[:_MAX_SCAN_CHARS]
    for fancy, plain in _SMART_QUOTES.items():
        if fancy in text:
            text = text.replace(fancy, plain)
    return text


def _strip_quoted_history(message_text: str) -> str:
    """Return only what the customer typed this time."""
    cut = len(message_text)
    for pattern in (_QUOTE_LINE_RE, _QUOTE_HEADER_RE):
        match = pattern.search(message_text)
        if match:
            cut = min(cut, match.start())
    return message_text[:cut]


def _is_shouting(message_text: str) -> bool:
    """True when the customer's own text is mostly shouted grievance words."""
    fresh = _strip_quoted_history(message_text or "")
    if not fresh:
        return False
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
        return True

    # Path 2 — sustained shouting with no single grievance word, e.g.
    # "I HAVE HAD IT WITH YOU AND THE WAY YOU AND THE TEAM TREAT ME".
    # Requires the whole message to be capitals AND to read like a sentence:
    # an address in capitals has no pronouns or verbs.
    if (len(all_caps) >= _SUSTAINED_MIN_CAPS
            and (len(all_caps) / len(all_words)) >= _SUSTAINED_MIN_RATIO
            and sum(1 for w in all_caps if w in _SHOUT_GRAMMAR) >= _SUSTAINED_MIN_GRAMMAR):
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
    raw_message = _normalise_text(payload.get("message_text"))
    raw_subject = _normalise_text(payload.get("ticket_subject"))
    message_text = raw_message.lower()
    ticket_subject = raw_subject.lower()
    combined_text = f"{ticket_subject} {message_text}"

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
    immediate_matches = _find_matches(combined_text, _IMMEDIATE_KEYWORDS)

    # Weak triggers are ordinary English ("missing", "lost", "without the").
    # They only escalate when the message also shows an order was placed or
    # delivered, and is not phrased as a browsing or care question.
    weak_allowed = _weak_triggers_apply(combined_text)
    weak_matches = _find_matches(combined_text, _WEAK_IMMEDIATE) if weak_allowed else []
    immediate_matches.extend(m for m in weak_matches if m not in immediate_matches)

    manager_matches = _find_matches(combined_text, _MANAGER_DEMAND_KEYWORDS)
    if (_ESCALATE_RE.search(combined_text)
            and not _ESCALATE_NEGATED_RE.search(combined_text)):
        manager_matches.append("escalate this")

    angry_matches = _find_matches(combined_text, _ANGRY_KEYWORDS)
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

        # Check for angry customer (2+ angry signals → force immediate)
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

        log_event(logger, "INFO", "Classifier: IMMEDIATE",
                  ticket_id=payload.get("ticket_id"),
                  reason="; ".join(reason_parts),
                  matched=matched)

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
    high_matches = _find_matches(combined_text, _HIGH_KEYWORDS)
    high_hits = len(high_matches)
    high_intent_hit = bool(intent_names & _HIGH_INTENTS)

    # Check for repeated follow-ups (3+ messages with no reply is CRITICAL in
    # the LLM prompt, but we can't count messages here — we look for the
    # follow-up keyword pattern as a HIGH signal)
    followup_match = _FOLLOWUP_PATTERN.search(combined_text)

    if high_hits > 0 or high_intent_hit or followup_match or exclaiming or shouting:
        high_sensitive = bool(intent_names & _HIGH_SENSITIVE_INTENTS) or bool(
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
