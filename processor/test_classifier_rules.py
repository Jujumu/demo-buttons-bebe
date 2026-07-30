"""Tests for the deterministic risk classifier, including the Fable rules merge.

Adapted from fable/tests/unit/test_risk_parity.py and test_risk.py, re-expressed
in main's lowercase vocabulary ("immediate" / "high" / "normal") and main's
payload-dict API. Fable's own classifier file is NOT used — only its rules were
merged into main's classifier, so a parity test against that file would be
meaningless here.

Three things are pinned:
  1. Every rule the Fable branch had and main did not now escalates.
  2. Nothing benign newly escalates — the word-boundary guards still hold.
  3. The classifier can only ESCALATE. A sensitive verdict always asks for an
     owner ping, and nothing here can clear a flag.

The 48-scenario regression at the bottom skips until the Task 1 harness merges.
"""

from __future__ import annotations

import json
import re
import sys
import unittest
from pathlib import Path

PROCESSOR_DIR = Path(__file__).resolve().parent
WEBHOOK_SRC = PROCESSOR_DIR.parent / "webhook" / "src"
sys.path[:0] = [str(PROCESSOR_DIR), str(WEBHOOK_SRC)]

import classifier as cls  # noqa: E402
from classifier import HIGH, IMMEDIATE, NORMAL, classify  # noqa: E402

SCENARIOS = PROCESSOR_DIR.parent / "testing" / "scenarios.json"
_RANK = {NORMAL: 0, HIGH: 1, IMMEDIATE: 2}


def _c(message: str, subject: str = "", intents=None) -> dict:
    return classify({
        "ticket_id": 1,
        "message_text": message,
        "ticket_subject": subject,
        "intents": intents or [],
    })


class BuiltInSelfTestTests(unittest.TestCase):
    """The self-test that `python classifier.py` runs must also pass in CI."""

    def test_selftest_passes(self):
        ok, total = cls._selftest()
        self.assertTrue(ok, "classifier self-test reported failures")
        self.assertGreater(total, 50)


# Every pattern this port adds, paired with a message that exercises it.
# The mutation test below removes each pattern in turn and asserts its exemplar
# stops escalating - so a rule that is already covered by a pre-existing
# pattern, or an exemplar that fires some OTHER rule, both fail loudly.
# Code review of the first version found 31 of 62 new patterns were deletable
# with the whole suite still green.
STRONG_EXEMPLARS = {
    r"\bcharge\s?-?\s?back\b": "I will charge back the payment.",
    r"\bcharged\s+back\b": "I have charged back the payment.",
    r"\breverse\s+the\s+(charge|payment)\b": "Please reverse the charge.",
    r"\bdisput(?:ing|ed)\b": "I am disputing this with my bank.",
    r"\bcontest\s+the\s+charge\b": "I will contest the charge.",
    r"\b(?:did\s+not|didn'?t|never|have\s+not|haven'?t)\s+authoris?z?e\w*\b":
        "I never authorised this payment.",
    r"\bunauthoris(?:ed|ing)\s+(charge|transaction|payment)\b":
        "There is an unauthorised transaction on my card.",
    r"\bunauthorized\s+transaction\b": "There is an unauthorized transaction.",
    r"\bfraudulent\b": "This looks fraudulent.",
    r"\bscamm(?:ed|er)\b": "I have been scammed.",
    r"\brip\s?off\b": "What a ripoff.",
    r"\bripped\s+me\s+off\b": "You ripped me off.",
    r"\bstole\s+my\s+money\b": "They stole my money.",
    r"\b(?:want|give\s+me|return)\s+my\s+money\b": "I want my money.",
    r"\byou\s+stole\b": "You stole from me.",
    r"\btheft\b": "This is theft.",
    r"\bsuing\b": "I am suing.",
    r"\blegal\s+counsel\b": "I have retained legal counsel.",
    r"\bcease\s+and\s+desist\b": "Consider this a cease and desist.",
    r"\bfile\s+a\s+complaint\b": "I will file a complaint.",
    r"\b(?:is\s?n'?t|was\s?n'?t|not)\s+what\s+i\s+ordered\b":
        "This isn't what I ordered.",
    r"\b(?:got|sent|received)\s+the\s+wrong\b": "She received the wrong bag.",
    r"\bnot\s+mine\b": "These are not mine.",
    r"\bnot\s+as\s+described\b": "It is not as described.",
    r"\blooks?\s+nothing\s+like\b": "It looks nothing like it.",
    r"\bnothing\s+like\s+the\s+(photo|picture|listing|description|website)\b":
        "Nothing like the photo.",
    r"\bbut\s+(?:i\s+)?got\s+(?:a|an|the)\s": "I picked blue but got a pink one.",
    r"\bbut\s+received\s+(?:a|an|the)\s": "I picked blue but received a pink one.",
    r"\binstead\s+i\s+got\b": "Instead I got the gown.",
    r"\bcracked\b": "It is cracked.",
    r"\bshattered\b": "It is shattered.",
    r"\bfrayed\b": "The hem is frayed.",
    r"\bfell\s+apart\b": "It fell apart.",
    r"\bseam\s+ripped\b": "The seam ripped.",
    r"\b(?:did\s+not|didn'?t)\s+come\s+with\b": "It didn't come with the bib.",
    r"\b(?:marked|says|shows|tracking\s+says)\s+(?:it\s+was\s+|as\s+)?delivered\s+but\b":
        "It is marked delivered but I have not seen it.",
    r"\bnothing\s+(?:is\s+)?here\b": "The courier says delivered, nothing is here.",
}

# Weak rules need order/delivery context, so every exemplar supplies some.
WEAK_EXEMPLARS = {
    r"\bmissing\b": "One item is missing from the parcel.",
    r"\blost\b": "My parcel seems lost.",
    r"\bwithout\s+the\b": "The set arrived without the headband.",
    r"\bnot\s+included\b": "The hat was not included in my order.",
    r"\bwas\s?n'?t\s+included\b": "The hat wasn't included in my order.",
    r"\bleft\s+out\b": "The socks were left out of the box.",
    r"\bsupposed\s+to\s+include\b": "My order was supposed to include a bib.",
    r"\bdifferent\s+item\b": "My parcel held a completely different item.",
    r"\binstead\s+of\s+the\b": "My parcel held the gown instead of the romper.",
    r"\bripped\b": "The parcel held a ripped bodysuit.",
    r"\bstained\b": "My order held a stained bib.",
    r"\ba\s+(?:hole|rip|tear|stain)\b(?!\s*-?\s*away)": "My parcel held a top with a stain.",
    r"\b(?:hole|rip|tear|stain)\s+(?:in|on)\b": "My parcel held a top with holes, hole in the arm.",
    r"\banother\s+customer\b": "The box is labelled for another customer.",
    r"\bsomeone\s+else'?s?\s+(order|name|items?|package|parcel|box)\b":
        "The box holds someone else's order.",
}

# The HIGH-tier rules this port added. Non-delivery sits at HIGH rather than
# IMMEDIATE on purpose: "I still haven't received it" is the commonest WISMO
# wording, and every one of those would otherwise page the owner.
PORTED_HIGH_EXEMPLARS = {
    r"\b(?:has\s?n'?t|has\s+not|have\s+not|have\s?n'?t)\s+(?:arrived|turned\s+up|shown\s+up)\b":
        "My parcels haven't arrived.",
    r"\bstill\s+(?:has\s?n'?t|have\s?n'?t|not)\s+(?:arrived|come|received)\b":
        "It still hasn't come.",
    r"\bnot\s+(?:been\s+)?delivered\b": "It was not delivered.",
    r"\bnothing\s+(?:has\s+|had\s+)?(?:arrived|come|turned\s+up|showed\s+up|been\s+delivered)\b":
        "Nothing has arrived.",
    r"\bwhere\s+my\s+(?:order|parcel|package|delivery|items?|stuff)\s+(?:is|are)\b":
        "Do you know where my parcel is?",
}

MANAGER_EXEMPLARS = {
    r"\b(?:speak|talk)\s+to\s+(?:a|your|the)\s+(?:manager|supervisor|owner)\b":
        "Let me talk to a manager.",
    r"\bget\s+me\s+(?:a|your|the)\s+(?:manager|supervisor|owner)\b":
        "Get me a manager.",
    r"\bwant\s+(?:a|to\s+speak\s+to\s+a)\s+manager\b": "I want a manager.",
    r"\byour\s+supervisor\b": "Put me through to your supervisor.",
    r"\bi\s+demand\b": "I demand an answer.",
    r"\b(?:owner|manager|supervisor)'?s?\s+(?:personal\s+)?"
    r"(?:phone|number|cell|mobile|email|address)\b":
        "Give me the owner's personal phone number.",
}


class SelfTestCorpusTests(unittest.TestCase):
    """The corpus that `python classifier.py` runs must also pass in CI."""

    def test_selftest_passes(self):
        ok, total = cls._selftest()
        self.assertTrue(ok, "classifier self-test reported failures")

    def test_every_selftest_case_matches_its_label(self):
        for message, want_priority, want_sensitive in cls._SELFTEST_CASES:
            with self.subTest(message=message[:60]):
                got = _c(message)
                self.assertEqual(got["priority"], want_priority, got["reason"])
                self.assertEqual(got["sensitive"], want_sensitive)


class EveryNewRuleIsLoadBearingTests(unittest.TestCase):
    """Mutation test: remove one new rule, its exemplar must stop escalating.

    This is what stops the suite drifting into vacuity. Adding a pattern
    without an exemplar fails `test_every_new_pattern_has_an_exemplar`;
    adding one that some other rule already covers fails the mutation check.
    """

    # Several tables are split in two at runtime - main's original rules and
    # the ones this port added read DIFFERENT views of the ticket - so
    # patching only the combined name is a no-op, and the mutation test would
    # pass while proving nothing. It did exactly that once already.
    _SPLIT_TABLES = {
        "_WEAK_IMMEDIATE": (
            "_WEAK_IMMEDIATE", "_WEAK_DAMAGE", "_WEAK_OMISSION"),
        "_IMMEDIATE_KEYWORDS": (
            "_IMMEDIATE_KEYWORDS", "_MAIN_IMMEDIATE_KEYWORDS",
            "_PORT_IMMEDIATE_KEYWORDS"),
        "_HIGH_KEYWORDS": (
            "_HIGH_KEYWORDS", "_MAIN_HIGH_KEYWORDS", "_PORT_HIGH_KEYWORDS"),
    }

    # Tables classify() never consults. A pattern surviving in one of these is
    # harmless, so the leak guard below ignores them.
    _NOT_READ_BY_CLASSIFY = frozenset({"_PORTED_HIGH_PATTERNS"})

    def _classify_without(self, attr: str, pattern: str, message: str) -> str:
        targets = list(self._SPLIT_TABLES.get(attr, (attr,)))
        originals = {name: getattr(cls, name) for name in targets}
        try:
            for name, original in originals.items():
                setattr(cls, name, [p for p in original if p != pattern])

            # Leak guard. If the pattern is still reachable from any table
            # classify() reads, the mutation did nothing and the caller's
            # assertion proves nothing. This fires the moment someone splits
            # another table without adding it to _SPLIT_TABLES above.
            leaked = sorted(
                name for name in dir(cls)
                if name.startswith("_") and name not in self._NOT_READ_BY_CLASSIFY
                and isinstance(getattr(cls, name, None), (list, tuple))
                and pattern in getattr(cls, name)
            )
            self.assertEqual(
                leaked, [],
                f"mutation of {attr} is a no-op: {pattern!r} is still live in "
                f"{leaked} - add them to _SPLIT_TABLES",
            )
            return _c(message)["priority"]
        finally:
            for name, original in originals.items():
                setattr(cls, name, original)

    def test_ported_high_tuple_is_derived_not_retyped(self):
        # _PORTED_HIGH_PATTERNS is exempt from the leak guard above, so pin it
        # to the real table instead - a hand-copied version drifted once.
        self.assertEqual(cls._PORTED_HIGH_PATTERNS, tuple(cls._PORT_HIGH_KEYWORDS))

    def test_split_tables_still_compose_the_combined_ones(self):
        self.assertEqual(
            cls._IMMEDIATE_KEYWORDS,
            cls._MAIN_IMMEDIATE_KEYWORDS + cls._PORT_IMMEDIATE_KEYWORDS)
        self.assertEqual(
            cls._HIGH_KEYWORDS,
            cls._MAIN_HIGH_KEYWORDS + cls._PORT_HIGH_KEYWORDS)
        self.assertEqual(
            cls._WEAK_IMMEDIATE, cls._WEAK_DAMAGE + cls._WEAK_OMISSION)

    def test_removing_a_ported_high_rule_stops_its_exemplar_escalating(self):
        for pattern, message in PORTED_HIGH_EXEMPLARS.items():
            with self.subTest(pattern=pattern):
                self.assertEqual(_c(message)["priority"], HIGH, message)
                self.assertLess(
                    _RANK[self._classify_without("_HIGH_KEYWORDS", pattern, message)],
                    _RANK[HIGH],
                    f"{pattern!r} is dead code - {message!r} is unchanged without it",
                )

    def test_every_new_pattern_has_an_exemplar(self):
        covered = (set(STRONG_EXEMPLARS) | set(WEAK_EXEMPLARS)
                   | set(MANAGER_EXEMPLARS) | set(PORTED_HIGH_EXEMPLARS))
        for pattern in cls._PORTED_HIGH_PATTERNS:
            self.assertIn(pattern, covered, f"ported HIGH rule has no exemplar: {pattern}")
            self.assertIn(pattern, cls._HIGH_KEYWORDS,
                          f"exemplar names a HIGH pattern not in the table: {pattern}")
        # Only the patterns this port added need exemplars. Main's originals
        # start above the ported block; compare against the known lists.
        for pattern in cls._WEAK_IMMEDIATE:
            self.assertIn(pattern, covered, f"weak rule has no exemplar: {pattern}")
        for pattern in cls._MANAGER_DEMAND_KEYWORDS:
            self.assertIn(pattern, covered, f"manager rule has no exemplar: {pattern}")
        for pattern in STRONG_EXEMPLARS:
            self.assertIn(pattern, cls._IMMEDIATE_KEYWORDS,
                          f"exemplar names a pattern that is not in the table: {pattern}")

    def test_removing_a_strong_rule_stops_its_exemplar_escalating(self):
        for pattern, message in STRONG_EXEMPLARS.items():
            with self.subTest(pattern=pattern):
                self.assertEqual(_c(message)["priority"], IMMEDIATE, message)
                self.assertLess(
                    _RANK[self._classify_without("_IMMEDIATE_KEYWORDS", pattern, message)],
                    _RANK[IMMEDIATE],
                    f"{pattern!r} is dead code - {message!r} is unchanged without it",
                )

    def test_removing_a_weak_rule_stops_its_exemplar_escalating(self):
        for pattern, message in WEAK_EXEMPLARS.items():
            with self.subTest(pattern=pattern):
                self.assertEqual(_c(message)["priority"], IMMEDIATE, message)
                self.assertLess(
                    _RANK[self._classify_without("_WEAK_IMMEDIATE", pattern, message)],
                    _RANK[IMMEDIATE],
                    f"{pattern!r} is dead code - {message!r} is unchanged without it",
                )

    def test_removing_a_manager_rule_stops_its_exemplar_escalating(self):
        for pattern, message in MANAGER_EXEMPLARS.items():
            with self.subTest(pattern=pattern):
                self.assertEqual(_c(message)["priority"], IMMEDIATE, message)
                self.assertLess(
                    _RANK[self._classify_without("_MANAGER_DEMAND_KEYWORDS", pattern, message)],
                    _RANK[IMMEDIATE],
                    f"{pattern!r} is dead code - {message!r} is unchanged without it",
                )


class WeakRulesNeedContextTests(unittest.TestCase):
    """The heart of the fix: ordinary words only count when an order exists."""

    def test_weak_word_alone_does_not_escalate(self):
        for message in [
            "Am I missing something? I can't find the size chart.",
            "I'm a bit lost, which size do I need for a 6 month old?",
            "I lost the discount code you emailed me, can you resend it?",
            "Can I order the romper without the bow?",
            "Do you sell the dress without the headband?",
            "Are duties and taxes not included in the price?",
            "How do I get a stain out of a cotton onesie?",
            "What is the best way to remove a stain on white muslin?",
            "Can I exchange it for a different item?",
            "Can I get the pink one instead of the blue one?",
            "I left out my apartment number when I placed the order.",
            "Another customer recommended your store to me!",
            "Do you have a tear-away label on the leggings?",
        ]:
            with self.subTest(message=message):
                result = _c(message)
                self.assertEqual(result["priority"], NORMAL, result["reason"])

    def test_the_same_word_with_an_order_escalates(self):
        for message in [
            "One item is missing from the parcel.",
            "My parcel seems lost.",
            "The romper set arrived without the matching headband.",
            "The hat was not included in my order.",
            "The socks were left out of the box.",
            "My parcel held a completely different item.",
            "The box is labelled for another customer.",
        ]:
            with self.subTest(message=message):
                self.assertEqual(_c(message)["priority"], IMMEDIATE)

    def test_damage_evidence_beats_the_browsing_guard(self):
        """Nobody says "arrived ripped" while browsing."""
        for message in [
            "Do you sell a replacement bow? Mine arrived ripped.",
            "Am I able to swap this? The parcel had a stained romper in it.",
            "Can I ask why my order came without the hat?",
            "Do you know if my parcel is missing? It says delivered but there is nothing here.",
        ]:
            with self.subTest(message=message):
                self.assertEqual(_c(message)["priority"], IMMEDIATE)

    def test_a_babys_age_is_not_a_delivery_delay(self):
        """This is a baby-clothes store: "my 6 week old" is in every second
        message, and a bare duration used to unlock the weak rules."""
        for message in [
            "The parcel came today and I love it. Can I order the sleepsuit "
            "without the bow for my 6 week old?",
            "My package arrived 3 days ago and it is lovely, can I order the "
            "same romper without the bow for my sister?",
            "My order arrived 2 days ago. Do you sell the dress without the headband?",
            "Do you ship within 3 days? My order arrived without the gift note last time.",
        ]:
            with self.subTest(message=message[:50]):
                self.assertEqual(_c(message)["priority"], NORMAL)

    def test_a_politely_phrased_complaint_still_escalates(self):
        """The browsing guard must yield to a real delivery problem."""
        for message in [
            "Is it possible the courier lost my parcel? Tracking stopped 8 days ago.",
            "Can I ask why my parcel arrived with a huge stain on it?",
            "Am I able to get a refund, the dress arrived torn?",
            "Do you know where my order is? Nothing has arrived and it has been 3 weeks.",
        ]:
            with self.subTest(message=message):
                self.assertNotEqual(_c(message)["priority"], NORMAL)

    def test_a_browsing_question_never_unlocks_the_weak_rules(self):
        # Even with an order word present, a "can I / do you" question is a
        # request, not a complaint.
        self.assertEqual(
            _c("My order arrives Friday - can I add a hat without the bow?")["priority"],
            NORMAL)

    def test_strong_rules_ignore_the_browsing_guard(self):
        # A refund or damage report is a complaint however it is phrased.
        for message in ["Can I get a refund? My order arrived damaged.",
                        "Do you handle this? I am filing a chargeback.",
                        "How do I return this? It isn't what I ordered."]:
            with self.subTest(message=message):
                self.assertEqual(_c(message)["priority"], IMMEDIATE)


class SmartPunctuationTests(unittest.TestCase):
    """Apple, Gmail and Outlook all substitute a curly apostrophe."""

    PAIRS = [
        "I didn't receive my order.",
        "This isn't what I ordered at all.",
        "The set didn't come with the headband.",
        "Give me the owner's personal phone number.",
        "I haven't received my order.",
        "The box holds someone else's order.",
        "The hat wasn't included in my order.",
    ]

    def test_curly_and_straight_apostrophes_agree(self):
        for straight in self.PAIRS:
            curly = straight.replace("'", "\u2019")
            with self.subTest(message=straight):
                self.assertEqual(_c(straight)["priority"], _c(curly)["priority"],
                                 f"curly apostrophe changed the verdict: {straight}")
                self.assertNotEqual(_c(curly)["priority"], NORMAL)


class StructuralAngerTests(unittest.TestCase):
    """Anger expressed with punctuation and capitals, not words."""

    def test_triple_exclamation_escalates_without_any_angry_word(self):
        result = _c("Where is my stuff!!!")
        self.assertGreaterEqual(_RANK[result["priority"]], _RANK[HIGH])
        self.assertIn("!!!", result["matched"])

    def test_enthusiasm_is_not_anger(self):
        for message in ["Thank you so much!!! The dress is perfect!!!",
                        "Just received it and I LOVE IT!!! Best purchase ever!!!",
                        "OBSESSED!!! So cute!!!"]:
            with self.subTest(message=message):
                self.assertEqual(_c(message)["priority"], NORMAL)

    def test_one_or_two_exclamations_do_not_escalate(self):
        for message in ["Thanks so much!", "Love it!!"]:
            with self.subTest(message=message):
                self.assertEqual(_c(message)["priority"], NORMAL)

    def test_exclamation_in_the_subject_is_not_the_customers(self):
        # A customer replying to the store's own "FLASH SALE!!!" promo.
        result = _c("Do you restock the cream romper?",
                    subject="Re: FLASH SALE!!! 30% OFF EVERYTHING")
        self.assertEqual(result["priority"], NORMAL)

    def test_shouting_escalates(self):
        for message in ["WHY HAS NOBODY ANSWERED ME PLEASE REPLY TODAY",
                        "THIS IS A JOKE", "PICK UP THE PHONE",
                        "I HAVE HAD IT WITH YOU AND THE WAY YOU AND THE TEAM TREAT ME"]:
            with self.subTest(message=message):
                self.assertGreaterEqual(_RANK[_c(message)["priority"]], _RANK[HIGH])

    def test_caps_lock_questions_are_not_shouting(self):
        """Caps lock is a habit; anger is a word choice."""
        for message in [
            "DO YOU SHIP TO CANADA AND HOW MUCH IS IT",
            "WHAT SIZE FOR A 6 MONTH OLD",
            "PLEASE SEND ME THE SIZE CHART",
            "HOW LONG IS DELIVERY TO IRELAND",
            "PLEASE ADD A GIFT NOTE THAT SAYS WELCOME BABY",
            "PLEASE HELP",
            "MY BABY IS SO CUTE IN THIS",
            "THANK YOU SO MUCH I AM SO HAPPY WITH MY ORDER",
            "THANK YOU SO MUCH FOR THE FAST DELIVERY",
            "CAN YOU CONFIRM MY ORDER NUMBER PLEASE",
            "IS THE PINK ROMPER BACK IN STOCK YET",
        ]:
            with self.subTest(message=message):
                self.assertEqual(_c(message)["priority"], NORMAL)

    def test_short_caps_rants_still_escalate(self):
        for message in ["THIS IS A JOKE", "PICK UP THE PHONE",
                        "I HAVE HAD IT WITH YOU AND THE WAY YOU AND THE TEAM TREAT ME"]:
            with self.subTest(message=message):
                self.assertGreaterEqual(_RANK[_c(message)["priority"]], _RANK[HIGH])

    def test_enthusiasm_survives_a_stray_negative_word(self):
        """_NEGATIVE_RE used to contain "not", "no" and "still"."""
        for message in ["Perfect!!! No notes!!!",
                        "Thanks!!! Still obsessed with the little hat!!!",
                        "The dress is gorgeous!!! Not sure which size next time!!!",
                        "Lovely quality!!! I will not be shopping anywhere else!!!",
                        "Awesome!!!", "Best shop ever!!! So quick!!!"]:
            with self.subTest(message=message):
                self.assertEqual(_c(message)["priority"], NORMAL)

    def test_capitals_that_are_not_shouting(self):
        for message in [
            "Do you carry NUNA UPPABABY BUGABOO DOONA CYBEX MAXI COSI?",
            "ORDER 10322 JANE SMITH 42 MAPLE AVE TORONTO ONTARIO CANADA",
            "Do you ship via USPS UPS DHL FEDEX to the USA and is VAT included?",
            "Can I pay COD or do you need a PIN?",
        ]:
            with self.subTest(message=message):
                self.assertEqual(_c(message)["priority"], NORMAL)

    def test_all_caps_subject_alone_is_not_shouting(self):
        result = _c("Hi, when will my order ship? Thanks.",
                    subject="ORDER CONFIRMATION FROM BUTTONS BEBE ONLINE STORE")
        self.assertEqual(result["priority"], NORMAL)

    def test_quoted_history_does_not_dilute_a_rant(self):
        rant = "WHY HAS NOBODY REPLIED I HAVE BEEN WAITING WEEKS THIS IS RIDICULOUS"
        quoted = (rant + "\n\nOn Mon, Jul 20 2026 at 9:14 AM Buttons Bebe Support "
                  "wrote: thanks for reaching out, we will look into your order and "
                  "get back to you as soon as we can with an update on the delivery.")
        self.assertGreaterEqual(_RANK[_c(quoted)["priority"]], _RANK[HIGH])


class QuotedHistoryTests(unittest.TestCase):
    """Truncating at the first quote marker returned "" for every bottom-posted
    or inline reply - Outlook's default - which silently disabled both
    structural signals."""

    RANT = "WHERE IS IT I HAVE HAD ENOUGH OF WAITING THIS IS RIDICULOUS"

    def test_a_bottom_posted_rant_is_still_seen(self):
        for body in [
            f"> we are looking into it\n\n{self.RANT}",
            f"| we are looking into it\n\n{self.RANT}",
            f"On Mon, Jul 20 2026 at 9:14 AM Support wrote:\n> we are on it\n\n{self.RANT}",
            f"-------- Forwarded message --------\n> earlier text\n\n{self.RANT}",
        ]:
            with self.subTest(body=body[:40]):
                self.assertGreaterEqual(_RANK[_c(body)["priority"]], _RANK[HIGH])

    def test_a_top_posted_rant_is_not_diluted_by_the_thread(self):
        body = (self.RANT + "\n\nOn Mon, Jul 20 2026 at 9:14 AM Buttons Bebe "
                "Support wrote:\n> thanks for reaching out, we will look into "
                "your order and get back to you as soon as we can with an "
                "update on the delivery and the tracking number")
        self.assertGreaterEqual(_RANK[_c(body)["priority"]], _RANK[HIGH])

    def test_the_customers_own_prose_is_never_mistaken_for_a_quote_header(self):
        # "wrote:" mid-sentence is the customer talking, not a mail client.
        body = ("On Friday I ordered a gift set. Your colleague wrote: we will "
                "chase it. This is ridiculous!!!")
        self.assertGreaterEqual(_RANK[_c(body)["priority"]], _RANK[HIGH])

    def test_an_all_quoted_message_falls_back_to_the_whole_text(self):
        body = "> I want a refund, my order arrived damaged"
        self.assertEqual(_c(body)["priority"], IMMEDIATE)


class BottomPostedTests(unittest.TestCase):
    """The commonest reply shape in email: quote header on top, the customer's
    words under it, a sign-off at the end.

    A previous version dropped the paragraph directly under a quote header, on
    the theory that it was the quoted body. It deleted the customer's
    complaint in 100% of these - the trailing "Thanks, Jane" defeated the
    empty-result fallback, so nothing noticed.
    """

    HEADERS = [
        "On Mon, Jul 20, 2026 at 9:14 AM Buttons Bebe Support <hello@bb.com> wrote:",
        "From: Buttons Bebe <hello@bb.com>\nSubject: Re: your order",
        "-------- Forwarded message --------",
        "----- Original Message -----",
    ]
    SIGN_OFFS = ["Thanks,\nJane", "Kind regards,\nJane", "Jane", "Many thanks"]

    def test_a_complaint_under_a_quote_header_survives_a_sign_off(self):
        for header in self.HEADERS:
            for sign_off in self.SIGN_OFFS:
                body = (f"{header}\n\nMy parcel arrived damaged and I would "
                        f"like a refund.\n\n{sign_off}")
                with self.subTest(header=header[:24], sign_off=sign_off[:12]):
                    self.assertEqual(_c(body)["priority"], IMMEDIATE)

    def test_a_customer_quoting_their_own_earlier_complaint(self):
        """Keyword matching sees the whole message; only structural signals
        are limited to what the customer typed this time."""
        body = ("> I ordered a romper on the 3rd and it arrived damaged.\n\n"
                "Any update on this?")
        self.assertEqual(_c(body)["priority"], IMMEDIATE)

    def test_a_header_shaped_line_mid_body_does_not_truncate_the_complaint(self):
        body = ("Hi there,\n\nSubject: order 10322\n\n"
                "My parcel arrived damaged and I want a refund.")
        self.assertEqual(_c(body)["priority"], IMMEDIATE)

    def test_a_multi_paragraph_store_auto_reply_does_not_escalate_a_thank_you(self):
        """Only ONE paragraph used to be dropped, so a "Hi Jane," greeting ate
        the drop and the footer leaked as the customer's words."""
        body = ("From: Buttons Bebe <hello@bb.com>\nSubject: Re: your order\n\n"
                "Hi Jane,\n\nIf your order hasn't arrived within 5 working days, "
                "or an item is missing from your parcel, just reply to this "
                "email.\n\nThanks!")
        self.assertEqual(_c(body)["priority"], NORMAL)


class ReDoSTests(unittest.TestCase):
    """Ticket bodies are attacker-influenced and arrive before any human sees
    them. Every pattern applied to them must be linear."""

    def test_the_quote_header_pattern_is_bounded(self):
        import time
        # "<[^>]+@[^>]+>" nested two unbounded quantifiers: 72 SECONDS on 512KB.
        payload = "hi <" + "a@" * 40000
        started = time.perf_counter()
        _c(payload)
        elapsed = time.perf_counter() - started
        self.assertLess(elapsed, 1.0, f"{elapsed:.2f}s on {len(payload)} bytes")

    def test_classification_is_bounded_on_every_hostile_shape(self):
        import time
        shapes = ["following up ", "a stain ", "!!! ", "MISSING ", "> quoted\n",
                  "On 1 Jan 2026 x wrote:\n", "why ", "hi <a@", "\n\n"]
        for shape in shapes:
            payload = shape * 40000
            with self.subTest(shape=shape[:12]):
                started = time.perf_counter()
                _c(payload, subject=payload[:2000])
                self.assertLess(time.perf_counter() - started, 1.0)


class LengthCapTests(unittest.TestCase):
    """A plain head truncation was the one way this classifier could come out
    LOWER than main's - and the tail is exactly where a bottom-posting customer
    writes."""

    def test_a_signal_at_the_very_end_survives_the_cap(self):
        for body in [
            "x " * 40000 + " my order arrived damaged and I want a refund",
            "hi " * 30000 + "chargeback",
        ]:
            with self.subTest(length=len(body)):
                self.assertGreater(len(body), cls._MAX_SCAN_CHARS)
                self.assertEqual(_c(body)["priority"], IMMEDIATE)

    def test_a_long_real_thread_still_escalates(self):
        reply = ("Thanks for getting in touch, we are looking into this for you "
                 "and will come back as soon as we have an update.\n"
                 "> your earlier message\n")
        body = reply * 1000 + "\nI want a refund, my order arrived damaged."
        self.assertGreater(len(body), 2 * cls._MAX_SCAN_CHARS)
        self.assertEqual(_c(body)["priority"], IMMEDIATE)

    def test_the_cap_is_big_enough_to_be_useful(self):
        self.assertGreaterEqual(cls._MAX_SCAN_CHARS, 4000)


class QuotedStoreTextTests(unittest.TestCase):
    """The store's own words must never be classified as the customer's.

    Quoted-history stripping used to be gated on the length cap, so for every
    real-sized ticket the support footer was keyword-matched - and that footer
    says "if an item is missing from your parcel".
    """

    FOOTER = ("> Buttons Bebe - if your order hasn't arrived within 5 working "
              "days, or an item is\n> missing from your parcel, just reply to "
              "this email and we will sort it out.")

    def test_a_thanks_under_the_support_footer_stays_normal(self):
        self.assertEqual(_c(f"Thank you, got it!\n\n{self.FOOTER}")["priority"], NORMAL)

    def test_an_outlook_style_quote_block_is_not_the_customer(self):
        body = ("Thanks, all good!\n\nFrom: Buttons Bebe <hello@buttonsbebe.com>\n"
                "Subject: your order\n\nIf an item is missing from your parcel "
                "just reply.")
        self.assertEqual(_c(body)["priority"], NORMAL)

    def test_a_quoted_store_promo_does_not_escalate_the_question_below_it(self):
        body = ("From: Buttons Bebe <hello@buttonsbebe.com>\nSubject: FLASH SALE\n\n"
                "FLASH SALE!!! 30% OFF EVERYTHING!!! HURRY!!!\n\n"
                "Do you restock the cream romper?")
        self.assertEqual(_c(body)["priority"], NORMAL)

    def test_the_customers_own_complaint_under_a_quote_still_escalates(self):
        body = f"My order arrived damaged and I want a refund.\n\n{self.FOOTER}"
        self.assertEqual(_c(body)["priority"], IMMEDIATE)


class BoilerplateFilterNeverDeescalatesTests(unittest.TestCase):
    """The boilerplate filter must never hide text from MAIN's rules.

    A boilerplate phrase is not always the store talking. "%off" is in the
    pattern because shop footers advertise sales - but customers mention their
    discount code constantly, and "working days" / "terms and conditions" /
    "flash sale" / "unsubscribe" are all things a customer writes too.

    When such a sentence is its own paragraph AND some other paragraph
    survives, the empty-result fallback does not fire and the complaint is
    simply deleted. Measured against main's classifier on 4 238 messages of
    exactly this shape: 3 998 silent immediate -> normal de-escalations
    (94.3%). Splitting the tables so main's rules read the unfiltered text
    took that to 0.

    Every case below is IMMEDIATE or HIGH under main's classifier. If any of
    them comes back NORMAL, the port has made the system less safe than the
    code it is replacing - which is the one thing it may not do.
    """

    TAIL = "\n\nKind regards,\nSarah"

    IMMEDIATE_CASES = [
        "I used the 20% off code at checkout and the dress arrived damaged.",
        "I paid with the 15% off voucher and want a refund.",
        "The 10%off code applied but you sent the wrong size.",
        "It has been 7 working days and my parcel never arrived.",
        "Your terms and conditions say final sale but the romper is defective.",
        "I ordered in the flash sale and the onesie arrived torn.",
        "Please unsubscribe me, and also refund order 1042.",
        "Unsubscribe. This is a scam.",
        "Let us know when the refund lands, the item was damaged.",
        "We are looking into legal action, my package was stolen.",
        "Thanks for your patience but I am filing a chargeback.",
    ]

    HIGH_CASES = [
        "Five working days later and the item is still not received.",
        "I read the terms and conditions and this is urgent.",
        "I will hit reply again tomorrow - where is my order?",
    ]

    def test_poisoned_paragraphs_still_reach_immediate(self):
        for body in self.IMMEDIATE_CASES:
            with self.subTest(body=body):
                self.assertEqual(_c(body + self.TAIL)["priority"], IMMEDIATE, body)
                # And with the survivor above rather than below it.
                self.assertEqual(_c("Hi there,\n\n" + body)["priority"], IMMEDIATE, body)

    def test_poisoned_paragraphs_still_reach_at_least_high(self):
        for body in self.HIGH_CASES:
            with self.subTest(body=body):
                self.assertGreaterEqual(
                    _RANK[_c(body + self.TAIL)["priority"]], _RANK[HIGH], body)

    def test_the_filter_still_protects_the_new_rules(self):
        # The whole point of the filter: a store footer must not fire the
        # rules this port ADDED. "missing from your parcel" is _WEAK_OMISSION.
        footer = ("Thanks for reaching out! If an item is missing from your "
                  "parcel, just reply to this email and our customer care "
                  "team will sort it out.")
        self.assertEqual(_c(f"Thank you, all sorted!\n\n{footer}")["priority"], NORMAL)

    def test_main_rules_read_the_unfiltered_text(self):
        # Direct structural check, so this survives a rewording of the cases.
        seen = {}
        original = cls._find_matches

        def spy(text, patterns):
            if patterns is cls._MAIN_IMMEDIATE_KEYWORDS:
                seen["main"] = text
            elif patterns is cls._PORT_IMMEDIATE_KEYWORDS:
                seen["port"] = text
            return original(text, patterns)

        cls._find_matches = spy
        try:
            _c("I used the 20% off code and the dress arrived damaged.\n\nSarah")
        finally:
            cls._find_matches = original
        self.assertIn("20% off", seen["main"])
        self.assertNotIn("20% off", seen["port"])


class PurchaseHistoryTests(unittest.TestCase):
    """"I ordered from you last year" is history, not delivery evidence."""

    def test_history_alone_does_not_unlock_the_omission_rules(self):
        for message in [
            "I bought a gift card from you last month and I have lost the code.",
            "I ordered from you last year. The gift box option seems missing from checkout now.",
            "You sent me the newsletter twice and the discount code is missing from it.",
            "I ordered a few things at Christmas, I have lost track of what I still need.",
            "I ordered twice before and loved it! One tiny thing, the newsletter link is missing.",
            "I purchased a voucher and left out the recipient email by mistake.",
        ]:
            with self.subTest(message=message[:50]):
                self.assertEqual(_c(message)["priority"], NORMAL)

    def test_a_shipment_claim_is_still_evidence(self):
        for message in ["You sent a different item instead of the one I picked.",
                        "You packed the wrong size.",
                        "You shipped me the wrong colour."]:
            with self.subTest(message=message):
                self.assertEqual(_c(message)["priority"], IMMEDIATE)


class CapsPolitenessTests(unittest.TestCase):
    """Praise in capitals is common, and it uses the same words anger does.

    A deliberate trade, measured both ways. Removing the positive-sentiment
    veto from the anchor path caught a handful of all-caps sarcasm but
    escalated 19 of 20 genuinely grateful all-caps messages - and every one of
    those is a push notification to the owner's phone. The veto is back, with
    an exemption for anchors that essentially never appear in praise.
    """

    GRATEFUL = [
        "THANKS SO MUCH FOR THE QUICK REPLY",
        "STILL LOVING THE ROMPER THANK YOU",
        "SERIOUSLY THE CUTEST THING EVER THANK YOU",
        "WORTH EVERY PENNY MONEY WELL SPENT LOVE IT",
        "GORGEOUS QUALITY WORTH THE MONEY THANK YOU",
        "PLEASE PASS ON MY THANKS TO YOUR MANAGER LOVELY SERVICE",
        "PERFECT THANK YOU I WILL ORDER AGAIN IMMEDIATELY",
        "THANK YOU SO MUCH I AM SO HAPPY WITH MY ORDER",
        "THANK YOU SO MUCH FOR THE FAST DELIVERY",
        "SO PLEASED WITH THIS LITTLE SET THANK YOU",
    ]

    # Round-5 review measured 6 of these 20 paging the owner. Two causes:
    # the praise vocabulary for baby clothes was missing from _POSITIVE_RE
    # (worth, favourite, softest, comfy, glad, happier), and "never" counted
    # as a grievance word on its own, which cancelled the positive veto for
    # "NEVER BEEN HAPPIER" and made NEVER a hard anchor on top.
    GRATEFUL_ROUND5 = [
        "I HAVE NEVER BEEN HAPPIER WITH AN ORDER",
        "STILL MY FAVOURITE SHOP, THE SOFTEST COTTON",
        "I WAS WAITING FOR THIS RESTOCK AND IT WAS WORTH IT",
        "I WILL NEVER SHOP ANYWHERE ELSE, LOVE IT",
        "STILL WEARING IT EVERY DAY, SO SOFT",
        "ORDERED IMMEDIATELY AND SO GLAD I DID",
        "SO COMFY AND COSY, HIGHLY RECOMMEND",
        "TELL YOUR MANAGER THE PACKAGING IS BEAUTIFUL",
        "PLEASE REPLY WITH THE RESTOCK DATE, I LOVE THESE",
        "MONEY WELL SPENT, THE QUALITY IS AMAZING",
    ]

    HARD = [
        "THANK YOU BUT I WANT A REFUND NOW",
        "THANKS BUT THIS IS UNACCEPTABLE",
        "THANKS FOR THE REPLY BUT MY PARCEL IS STILL MISSING",
        "LOVELY SHOP BUT THIS IS A DISGRACE",
    ]

    # Loosening the veto must not cost any of these. Every one is all-caps
    # anger, and several use the exact words the praise list above uses.
    ANGRY = [
        "I WANT MY MONEY NOW",
        "THIS IS A JOKE",
        "PICK UP THE PHONE",
        "I HAVE HAD ENOUGH OF BEING IGNORED",
        "WHERE IS MY REFUND",
        "ABSOLUTELY UNACCEPTABLE SERVICE",
        "I HAVE HAD IT WITH YOU AND THE WAY YOU AND THE TEAM TREAT ME",
        "NOBODY HAS ANSWERED ME IN TWO WEEKS",
        "MY ORDER IS STILL MISSING AND NOBODY REPLIES",
        "THIS IS RIDICULOUS, I WANT A MANAGER",
        "I AM FURIOUS ABOUT THIS",
        "STILL NO ANSWER, THIS IS PATHETIC",
        "NEVER ORDERING FROM YOU AGAIN, WHAT A DISGRACE",
        "I HAVE WAITED THREE WEEKS AND PAID FOR EXPRESS",
        "I DEMAND A RESPONSE TODAY",
        "NOT WORTH THE MONEY, WHAT A WASTE",
    ]

    def test_grateful_capitals_never_page_the_owner(self):
        for message in self.GRATEFUL + self.GRATEFUL_ROUND5:
            with self.subTest(message=message):
                self.assertEqual(_c(message)["priority"], NORMAL)

    def test_a_hard_anchor_fires_through_the_politeness(self):
        for message in self.HARD:
            with self.subTest(message=message):
                self.assertGreaterEqual(_RANK[_c(message)["priority"]], _RANK[HIGH])

    def test_all_caps_anger_still_escalates(self):
        for message in self.ANGRY:
            with self.subTest(message=message):
                self.assertGreaterEqual(_RANK[_c(message)["priority"]], _RANK[HIGH])

    def test_never_alone_is_not_a_grievance_word(self):
        # The word by itself is as common in praise as in complaint.
        self.assertIsNone(cls._NEGATIVE_RE.search("never been happier"))
        self.assertIsNone(cls._NEGATIVE_RE.search("i will never shop elsewhere"))
        # ...but the complaint uses of it still count.
        for grievance in ("never received", "never arrived", "never replied",
                          "never ordering from you again", "never again"):
            self.assertIsNotNone(cls._NEGATIVE_RE.search(grievance), grievance)

    def test_never_received_still_reaches_immediate_by_keyword(self):
        # The narrowed _NEGATIVE_RE must not be load-bearing for real misses:
        # these are caught by main's keyword table, not by sentiment.
        for message in ("I NEVER RECEIVED MY ORDER", "THANK YOU BUT I NEVER GOT IT"):
            with self.subTest(message=message):
                self.assertEqual(_c(message)["priority"], IMMEDIATE)

    def test_the_hard_anchor_set_excludes_words_praise_uses(self):
        for soft in ("MONEY", "REPLY", "RESPONSE", "WAITING", "MANAGER",
                     "PHONE", "IMMEDIATELY", "URGENT", "SERIOUSLY", "STILL",
                     "NEVER"):
            self.assertNotIn(soft, cls._SHOUT_HARD_ANCHORS)
        for hard in ("REFUND", "SCAM", "FRAUD", "UNACCEPTABLE", "DISGRACE"):
            self.assertIn(hard, cls._SHOUT_HARD_ANCHORS)


class TuningConstantTests(unittest.TestCase):
    """Pin the numeric constants. Mutation testing found every one of them
    could be changed - in either direction - with the whole suite still green.
    """

    def test_caps_stopwords_cover_the_tokens_that_are_information(self):
        # These are the tokens that made an ordinary shipping question look
        # like shouting when they counted toward the caps ratio.
        for token in ("USPS", "DHL", "FEDEX", "VAT", "THE", "AND", "YOU", "MY"):
            self.assertIn(token, cls._CAPS_STOPWORDS)
        self.assertEqual(
            _c("Do you ship via USPS UPS DHL FEDEX to the USA and is VAT included?")["priority"],
            NORMAL)

    def test_the_shout_ratio_is_load_bearing(self):
        probe = ("hello i am WAITING on a REPLY about one small thing and "
                 "otherwise it is all completely ok")
        self.assertEqual(_c(probe)["priority"], NORMAL)
        original = cls._SHOUT_MIN_RATIO
        try:
            cls._SHOUT_MIN_RATIO = 0.01
            loosened = _c(probe)["priority"]
        finally:
            cls._SHOUT_MIN_RATIO = original
        self.assertNotEqual(loosened, NORMAL,
                            "_SHOUT_MIN_RATIO can be dropped to 0.01 with no effect")

    def test_the_sustained_ratio_is_load_bearing(self):
        probe = ("hello there i wanted to say that I HAVE HAD IT WITH YOU AND "
                 "THE WAY YOU TREAT ME but otherwise it is all ok and there is "
                 "nothing else i would change about any of it at the moment")
        self.assertEqual(_c(probe)["priority"], NORMAL)
        original = cls._SUSTAINED_MIN_RATIO
        try:
            cls._SUSTAINED_MIN_RATIO = 0.01
            loosened = _c(probe)["priority"]
        finally:
            cls._SUSTAINED_MIN_RATIO = original
        self.assertNotEqual(loosened, NORMAL,
                            "_SUSTAINED_MIN_RATIO can be dropped with no effect")

    def test_a_high_value_order_with_a_complaint_is_flagged(self):
        # The order-value threshold had no test at all: nothing passed order_data.
        payload = {"ticket_id": 1, "message_text": "my order arrived damaged",
                   "ticket_subject": "", "intents": []}
        rich = classify(payload, order_data={"total_price": "240.00"})
        self.assertEqual(rich["priority"], IMMEDIATE)
        self.assertIn("240", rich["reason"])
        cheap = classify(payload, order_data={"total_price": "12.00"})
        self.assertNotIn("high order value", cheap["reason"])

    def test_a_bad_order_total_does_not_crash(self):
        payload = {"ticket_id": 1, "message_text": "my order arrived damaged",
                   "ticket_subject": "", "intents": []}
        for total in ("", None, "abc", {}, []):
            with self.subTest(total=total):
                self.assertEqual(classify(payload, order_data={"total_price": total})["priority"],
                                 IMMEDIATE)

    def test_the_scan_window_covers_a_realistic_ticket(self):
        # 8000 was small enough to lose anything written in the MIDDLE of a
        # long thread, which was a strict de-escalation against main.
        self.assertGreaterEqual(cls._MAX_SCAN_CHARS, 50_000)
        body = ("Hi there, hope you are well. " * 250
                + "The romper you sent arrived damaged and I would like a refund. "
                + "Anyway, do you restock the sage range? " * 250)
        self.assertGreater(len(body), 16_000)
        self.assertEqual(_c(body)["priority"], IMMEDIATE)

    def _seam_probe(self, before: str, after: str) -> str:
        """Build a message whose truncation seam falls EXACTLY between the two
        fragments, computed from the live constants so the test cannot go
        vacuous if the cap or the split ratio changes."""
        head_len = cls._MAX_SCAN_CHARS * 3 // 4
        tail_len = cls._MAX_SCAN_CHARS - head_len - len(cls._TRUNCATION_SENTINEL)
        head = ("ab " * head_len)[:head_len - len(before)] + before
        tail = after + (" cd" * tail_len)[:tail_len - len(after)]
        body = head + " middle " * 500 + tail
        self.assertEqual(len(head), head_len)
        self.assertEqual(len(tail), tail_len)
        self.assertGreater(len(body), cls._MAX_SCAN_CHARS)
        bounded = cls._bound(body)
        self.assertIn(before + cls._TRUNCATION_SENTINEL + after, bounded,
                      "the probe did not land on the seam")
        return body

    def test_the_seam_cannot_join_two_fragments_into_a_word(self):
        # Every pattern uses \s+, which matches a newline, so a "\n" sentinel
        # let the splice invent a phrase present in neither half.
        self.assertEqual(_c(self._seam_probe("for your  wrong", "size guide"))["priority"],
                         NORMAL)

    def test_the_seam_cannot_supply_a_word_boundary(self):
        # A punctuation-only sentinel closed the \s+ splice but not the \b
        # splice: "...abnon-refund" + "able..." matched "refund".
        self.assertEqual(_c(self._seam_probe("abnon-refund", "able"))["priority"], NORMAL)
        self.assertEqual(_c(self._seam_probe("xundam", "aged parcel"))["priority"], NORMAL)

    def test_a_follow_up_late_in_a_long_message_still_counts(self):
        body = ("Hi there, hope you are well and that the shop is doing nicely. " * 200
                + " Just following up again, still no response from anyone.")
        self.assertGreater(len(body), 8000)
        self.assertGreaterEqual(_RANK[_c(body)["priority"]], _RANK[HIGH])

    def test_the_negative_word_list_is_load_bearing(self):
        angry = "This is a disgrace!!! I am furious!!!"
        original = cls._NEGATIVE_RE
        try:
            cls._NEGATIVE_RE = re.compile(r"(?!x)x")   # never matches
            stubbed = _c("Lovely shop but this is a disgrace!!!")["priority"]
        finally:
            cls._NEGATIVE_RE = original
        self.assertNotEqual(stubbed, _c("Lovely shop but this is a disgrace!!!")["priority"],
                            "_NEGATIVE_RE can be stubbed out with no effect")


class AuditListTests(unittest.TestCase):
    """The mutation test iterates _PORTED_HIGH_PATTERNS, so emptying that tuple
    would disable the audit rather than fail it."""

    def test_the_ported_high_audit_list_is_not_empty(self):
        self.assertEqual(len(cls._PORTED_HIGH_PATTERNS), 5)
        for pattern in cls._PORTED_HIGH_PATTERNS:
            self.assertIn(pattern, cls._HIGH_KEYWORDS)

    def test_the_weak_tables_are_not_empty(self):
        self.assertGreaterEqual(len(cls._WEAK_DAMAGE), 5)
        self.assertGreaterEqual(len(cls._WEAK_OMISSION), 7)
        self.assertEqual(sorted(cls._WEAK_IMMEDIATE),
                         sorted(cls._WEAK_DAMAGE + cls._WEAK_OMISSION))


class NegationTests(unittest.TestCase):
    def test_asking_not_to_escalate_is_not_an_escalation(self):
        self.assertEqual(
            _c("Please don't escalate this, I just have a quick sizing question.")["priority"],
            NORMAL)

    def test_asking_to_escalate_still_is(self):
        self.assertEqual(
            _c("Please escalate this to someone who can help.")["priority"], IMMEDIATE)


class BoundedWorkTests(unittest.TestCase):
    """Ticket bodies are attacker-influenced."""

    def test_classify_is_bounded_on_a_hostile_message(self):
        import time
        # This shape backtracks super-linearly against a pre-existing pattern.
        payload = "following up " * 20000 + "q" * 5000
        started = time.perf_counter()
        _c(payload)
        elapsed = time.perf_counter() - started
        self.assertLess(elapsed, 1.0, f"classify took {elapsed:.2f}s on {len(payload)} bytes")

    def test_a_long_message_is_still_classified(self):
        padding = "hello there this is a normal sentence. " * 500
        self.assertEqual(_c("I want a refund. " + padding)["priority"], IMMEDIATE)


class ContractTests(unittest.TestCase):
    """The classifier's shape must not drift — the orchestrator depends on it."""

    REQUIRED_KEYS = {"priority", "reason", "sensitive", "should_draft",
                     "should_notify_owner", "source", "matched"}

    def test_every_verdict_has_the_full_shape(self):
        for message in ["I want a refund", "urgent please", "what brands do you carry?"]:
            with self.subTest(message=message):
                result = _c(message)
                self.assertEqual(set(result), self.REQUIRED_KEYS)
                self.assertIn(result["priority"], (IMMEDIATE, HIGH, NORMAL))
                self.assertIsInstance(result["matched"], list)

    def test_sensitive_always_notifies_the_owner(self):
        for message in ["I want a refund", "chargeback", "my order arrived damaged"]:
            with self.subTest(message=message):
                result = _c(message)
                self.assertTrue(result["sensitive"])
                self.assertTrue(result["should_notify_owner"])

    def test_classifier_never_suppresses_a_draft(self):
        # main's contract: this classifier may escalate, never stop a draft.
        for message in ["", "thanks", "chargeback", "SHOUTING AT YOU RIGHT NOW OK"]:
            with self.subTest(message=message):
                self.assertTrue(_c(message)["should_draft"])


@unittest.skipUnless(SCENARIOS.is_file(),
                     f"{SCENARIOS} not present — merge the Task 1 test harness first")
class ScenarioRegressionTests(unittest.TestCase):
    """Run the 48 harness scenarios through the classifier.

    This is the offline half of the tasklist's Task 4 acceptance test: every
    sensitive case must escalate on the code path alone, and nothing benign may
    newly escalate.
    """

    @classmethod
    def setUpClass(cls):
        cls.scenarios = json.loads(SCENARIOS.read_text(encoding="utf-8"))

    def _classify(self, scenario):
        return _c(scenario["message"], scenario.get("subject", ""))

    def test_every_sensitive_scenario_escalates(self):
        sensitive = [s for s in self.scenarios if s["cat"] == "sensitive"]
        self.assertGreaterEqual(len(sensitive), 10)
        for scenario in sensitive:
            with self.subTest(scenario=scenario["id"]):
                result = self._classify(scenario)
                self.assertNotEqual(
                    result["priority"], NORMAL,
                    msg=f"{scenario['id']} would not escalate: {scenario['message'][:80]}",
                )

    def test_benign_scenarios_do_not_escalate(self):
        # The harness's deliberately-benign cases: an empty message, a bare
        # thanks, and an obvious spam blast.
        for scenario_id in ("E01", "E02", "E12"):
            scenario = next((s for s in self.scenarios if s["id"] == scenario_id), None)
            if scenario is None:
                continue
            with self.subTest(scenario=scenario_id):
                self.assertEqual(self._classify(scenario)["priority"], NORMAL)


if __name__ == "__main__":
    unittest.main()
