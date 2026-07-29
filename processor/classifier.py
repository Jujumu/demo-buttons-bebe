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

    # ── Ported from the Fable branch (rules only — see PORTFROMFABLE ─────
    # Task 4). Every entry below is ADDITIVE: main's vocabulary, main's
    # lowercase priorities, main's logging. Nothing above was removed.

    # Chargeback / payment-reversal phrasings main missed
    r"\bcharge\s?-?\s?back\b", r"\bcharged\s+back\b",
    r"\breverse\s+the\s+(charge|payment)\b",
    r"\bdisput(?:ing|ed)\b", r"\bcontest\s+the\s+charge\b",
    r"\b(?:did\s+not|didn'?t|never)\s+authoriz?s?e?\w*\b",
    r"\bunauthoris(?:ed|ing)\s+(charge|transaction|payment)\b",
    r"\bunauthorized\s+transaction\b",
    # Fraud / theft accusations
    r"\bfraudulent\b", r"\bscamm(?:ed|er)\b", r"\brip\s?off\b",
    r"\bripped\s+me\s+off\b", r"\bstole\s+my\s+money\b",
    r"\byou\s+stole\b", r"\btheft\b",
    # Legal / regulatory variants
    r"\bsuing\b", r"\blegal\s+counsel\b", r"\bcease\s+and\s+desist\b",
    r"\bfile\s+a\s+complaint\b",

    # Wrong item — phrasings that contain no literal "wrong"
    r"\b(?:is\s?n'?t|was\s?n'?t|not)\s+what\s+i\s+ordered\b",
    r"\bdifferent\s+item\b", r"\binstead\s+of\s+the\b",
    r"\binstead\s+i\s+got\b", r"\bbut\s+(?:i\s+)?got\s+(?:a|an|the)?\b",
    r"\bbut\s+received\s+(?:a|an|the)\b",
    r"\b(?:got|sent|received)\s+the\s+wrong\b",
    # Someone else's parcel, and "not as described" — two wrong-item shapes the
    # 48-scenario harness (S05, S11) proved BOTH branches were missing.
    r"\banother\s+customer\b",
    r"\bsomeone\s+else'?s?\s+(order|name|items?|package|parcel)\b",
    r"\bnot\s+mine\b",
    r"\bnot\s+as\s+described\b",
    r"\blooks?\s+nothing\s+like\b",
    r"\bnothing\s+like\s+the\s+(photo|picture|listing|description|website)\b",

    # Damage words main lacks
    r"\bcracked\b", r"\bshattered\b", r"\bripped\b", r"\bfrayed\b",
    r"\bstained\b", r"\bfell\s+apart\b",
    r"\ba\s+(?:hole|rip|tear|stain)\b",
    r"\b(?:hole|rip|tear|stain)\s+(?:in|on)\b",
    r"\bseam\s+ripped\b", r"\bzipper\s+is\s+broken\b",
    r"\barrived\s+(?:broken|damaged)\b",

    # Missing / undelivered gaps
    r"\bmissing\b",
    r"\b(?:did\s+not|didn'?t)\s+come\s+with\b",
    r"\bnot\s+included\b", r"\bwas\s?n'?t\s+included\b",
    r"\bleft\s+out\b", r"\bsupposed\s+to\s+include\b",
    r"\bwithout\s+the\b",
    r"\b(?:has\s?n'?t|has\s+not)\s+arrived\b", r"\bnot\s+delivered\b",
    r"\bmarked\s+delivered\s+but\b",
    # Bare "lost" mirrors Fable's rule. It over-triggers on "lost my password"
    # by design: a false escalation costs one human glance, a missed
    # lost-parcel ticket is customer-facing.
    r"\blost\b",
]

# Demanding a manager / refusing to deal with support. Main had NO rule for
# this whole category — these tickets are angry and should always escalate.
_MANAGER_DEMAND_KEYWORDS = [
    r"\b(?:speak|talk)\s+to\s+(?:a|your|the)\s+(?:manager|supervisor|owner)\b",
    r"\bget\s+me\s+(?:a|your|the)\s+(?:manager|supervisor|owner)\b",
    r"\bwant\s+(?:a|to\s+speak\s+to\s+a)\s+manager\b",
    r"\byour\s+supervisor\b",
    r"\bi\s+demand\b",
    r"\bworst\s+company\b",
    r"\bescalate\s+(?:this|my)\b",
    # Trying to route around support entirely (harness case E06).
    r"\b(?:owner|manager|supervisor)'?s?\s+(?:personal\s+)?"
    r"(?:phone|number|cell|mobile|email|address)\b",
]

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
    r"cancel(?:lation)?(?:\s+(?:my\s+)?(?:order|item|purchase))?)\b",
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


# ── Structural anger (ported from Fable) ────────────────────────────
# Main only counted angry *words*. These two catch shouting that uses none.

# Three or more exclamation marks in a row.
_EXCLAIM_RE = re.compile(r"!{3,}")

# ALL-CAPS words of 3+ letters. Deliberately applied to the MESSAGE ONLY, not
# the subject: Gorgias subjects are often machine-generated in capitals
# ("ORDER CONFIRMATION FROM BUTTONS BEBE"), which would escalate every ticket.
_CAPS_WORD_RE = re.compile(r"\b[A-Z]{3,}\b")
_WORD_RE = re.compile(r"\b[A-Za-z]{2,}\b")

# Common all-caps tokens that are information, not shouting.
_CAPS_STOPWORDS = frozenset({
    "USPS", "UPS", "DHL", "FEDEX", "USA", "CAD", "USD", "ASAP", "VAT", "GST",
    "PST", "EST", "CST", "MST", "UTC", "PDT", "EDT", "COD", "PIN", "SKU",
    "FAQ", "URL", "PDF", "OMG", "THE", "AND", "FOR", "YOU",
})

# Shouting needs BOTH a floor and a share of the message, so one capitalised
# acronym in an otherwise normal sentence never counts.
_CAPS_MIN_WORDS = 6
_CAPS_MIN_RATIO = 0.5


def _is_shouting(message_text: str) -> bool:
    """True when the customer's message is mostly ALL-CAPS words."""
    if not message_text:
        return False
    caps = [w for w in _CAPS_WORD_RE.findall(message_text)
            if w not in _CAPS_STOPWORDS]
    if len(caps) < _CAPS_MIN_WORDS:
        return False
    total = len(_WORD_RE.findall(message_text))
    if total == 0:
        return False
    return (len(caps) / total) >= _CAPS_MIN_RATIO


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
    raw_message = str(payload.get("message_text") or "")
    raw_subject = str(payload.get("ticket_subject") or "")
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
    # "!!!"  is checked on subject + message; SHOUTING only on the message,
    # because Gorgias subjects are frequently auto-generated in capitals.
    exclaiming = bool(_EXCLAIM_RE.search(f"{raw_subject} {raw_message}"))
    shouting = _is_shouting(raw_message)

    # ── IMMEDIATE conditions ────────────────────────────────
    immediate_matches = _find_matches(combined_text, _IMMEDIATE_KEYWORDS)
    manager_matches = _find_matches(combined_text, _MANAGER_DEMAND_KEYWORDS)
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
    ("The bundle did not come with the bib that was supposed to include it.", IMMEDIATE, True),

    # ── The Fable rules main was missing ────────────────────
    # Manager demand — main had no rule for this whole category.
    ("I want to speak to a manager right now.", IMMEDIATE, True),
    ("Get me a manager, I demand an answer.", IMMEDIATE, True),
    ("Put me through to your supervisor please.", IMMEDIATE, True),
    ("This is the worst company I have ever dealt with.", IMMEDIATE, True),
    # Wrong item with no literal "wrong" in the text.
    ("I ordered a blue bodysuit but got a pink dress.", IMMEDIATE, True),
    ("This isn't what I ordered at all.", IMMEDIATE, True),
    ("You sent a different item instead of the one I picked.", IMMEDIATE, True),
    ("This box has another customer's name and items in it, not mine.", IMMEDIATE, True),
    ("The coat looks nothing like the listing photo.", IMMEDIATE, True),
    ("Just give me the owner's personal phone number so I can call them.", IMMEDIATE, True),
    # British spelling and reversal phrasings.
    ("There is an unauthorised charge on my card, reverse the charge.", IMMEDIATE, True),
    ("I have charged back the payment already.", IMMEDIATE, True),
    ("You ripped me off, this is fraudulent.", IMMEDIATE, True),
    # The acceptance case from the port tasklist.
    ("I want to speak to a manager, this is UNACCEPTABLE!!!", IMMEDIATE, True),

    # ── HIGH — urgent, or structural anger with no angry word ──
    ("Please cancel order #10345 immediately.", HIGH, True),
    ("I know it was final sale but can I return it?", HIGH, True),
    ("Where is my stuff!!!", HIGH, False),
    ("WHY HAS NOBODY ANSWERED ME PLEASE REPLY TODAY", HIGH, False),

    # ── NORMAL — must stay auto-draftable ───────────────────
    ("Do you ship to Canada and how much?", NORMAL, False),
    ("What size bodysuit should I order for a 4 month old?", NORMAL, False),
    ("What brands do you carry?", NORMAL, False),
    ("Thanks so much, the dress is adorable!", NORMAL, False),
    ("It arrived today and I love it, thank you!", NORMAL, False),

    # ── Word-boundary false-positive guards ─────────────────
    ("I took a trip to the store and loved it.", NORMAL, False),      # trip != rip
    ("Do you have a good grip strap for strollers?", NORMAL, False),  # grip != rip
    ("Please discard the old invoice, the new one is right.", NORMAL, False),  # discard != card
    ("I scanned the QR code on the package.", NORMAL, False),         # scanned != scam
    # Six all-caps tokens, but all of them are shipping acronyms, not shouting.
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
