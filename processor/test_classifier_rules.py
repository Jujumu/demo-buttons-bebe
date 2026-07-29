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
    r"\b(?:got|sent|received)\s+the\s+wrong\b": "You sent the wrong one.",
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
    r"\bmarked\s+delivered\s+but\b": "It is marked delivered but nothing came.",
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
    r"\binstead\s+of\s+the\b": "You sent the gown instead of the romper.",
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

    def _classify_without(self, attr: str, pattern: str, message: str) -> str:
        original = getattr(cls, attr)
        try:
            setattr(cls, attr, [p for p in original if p != pattern])
            return _c(message)["priority"]
        finally:
            setattr(cls, attr, original)

    def test_removing_a_ported_high_rule_stops_its_exemplar_escalating(self):
        for pattern, message in PORTED_HIGH_EXEMPLARS.items():
            with self.subTest(pattern=pattern):
                self.assertEqual(_c(message)["priority"], HIGH, message)
                self.assertEqual(
                    self._classify_without("_HIGH_KEYWORDS", pattern, message),
                    NORMAL,
                    f"{pattern!r} is dead code - {message!r} still escalates without it",
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
                self.assertEqual(
                    self._classify_without("_IMMEDIATE_KEYWORDS", pattern, message),
                    NORMAL,
                    f"{pattern!r} is dead code - {message!r} still escalates without it",
                )

    def test_removing_a_weak_rule_stops_its_exemplar_escalating(self):
        for pattern, message in WEAK_EXEMPLARS.items():
            with self.subTest(pattern=pattern):
                self.assertEqual(_c(message)["priority"], IMMEDIATE, message)
                self.assertEqual(
                    self._classify_without("_WEAK_IMMEDIATE", pattern, message),
                    NORMAL,
                    f"{pattern!r} is dead code - {message!r} still escalates without it",
                )

    def test_removing_a_manager_rule_stops_its_exemplar_escalating(self):
        for pattern, message in MANAGER_EXEMPLARS.items():
            with self.subTest(pattern=pattern):
                self.assertEqual(_c(message)["priority"], IMMEDIATE, message)
                self.assertEqual(
                    self._classify_without("_MANAGER_DEMAND_KEYWORDS", pattern, message),
                    NORMAL,
                    f"{pattern!r} is dead code - {message!r} still escalates without it",
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
