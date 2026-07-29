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


class NewImmediateRuleTests(unittest.TestCase):
    """Rules Fable had and main did not. Each must reach IMMEDIATE."""

    CASES = {
        # Manager / escalation demands — an entire category main lacked.
        "manager": "I want to speak to a manager right now.",
        "get-me-a-manager": "Get me a manager please.",
        "supervisor": "Put me through to your supervisor.",
        "i-demand": "I demand a full explanation today.",
        "worst-company": "This is the worst company I have ever used.",
        "bypass-support": "Give me the owner's personal phone number.",
        # Wrong item with no literal "wrong".
        "not-what-i-ordered": "This isn't what I ordered at all.",
        "but-got-a": "I ordered a blue bodysuit but got a pink dress.",
        "instead-of-the": "You sent the gown instead of the romper.",
        "different-item": "A completely different item turned up.",
        "someone-elses": "This box has another customer's name on it.",
        "not-as-described": "The coat is not as described.",
        "nothing-like": "It looks nothing like the listing.",
        # Damage words main lacked.
        "cracked": "The mug arrived cracked.",
        "shattered": "The frame was shattered in transit.",
        "ripped": "The seam ripped after one wear.",
        "frayed": "The hem is frayed already.",
        "stained": "The bib arrived stained.",
        "fell-apart": "The outfit fell apart in the wash.",
        "a-hole": "There is a hole in the sleeve.",
        "hole-in": "A hole in the knee of the leggings.",
        "zipper": "The zipper is broken.",
        # Missing / undelivered gaps.
        "bare-missing": "One item is missing from the parcel.",
        "didnt-come-with": "The set didn't come with the headband.",
        "not-included": "The matching hat was not included.",
        "left-out": "The socks were left out of the box.",
        "hasnt-arrived": "My parcel hasn't arrived yet.",
        "not-delivered": "The order was not delivered.",
        "marked-delivered": "Tracking says marked delivered but nothing came.",
        "bare-lost": "I think the parcel is lost.",
        # Fraud, dispute and legal variants.
        "charged-back": "I have charged back the payment.",
        "reverse-charge": "Please reverse the charge on my card.",
        "disputing": "I am disputing this with my bank.",
        "never-authorized": "I never authorized this payment.",
        "unauthorised-british": "There is an unauthorised charge on my card.",
        "scammed": "I have been scammed.",
        "ripped-me-off": "You ripped me off.",
        "stole-my-money": "You stole my money.",
        "cease-and-desist": "Consider this a cease and desist.",
        "file-a-complaint": "I will file a complaint.",
    }

    def test_each_new_rule_reaches_immediate(self):
        for label, message in self.CASES.items():
            with self.subTest(rule=label):
                result = _c(message)
                self.assertEqual(result["priority"], IMMEDIATE, msg=message)
                self.assertTrue(result["sensitive"])
                self.assertTrue(result["should_notify_owner"])
                self.assertTrue(result["matched"], "audit trail must not be empty")

    def test_acceptance_case_from_the_port_tasklist(self):
        result = _c("I want to speak to a manager, this is UNACCEPTABLE!!!")
        self.assertEqual(result["priority"], IMMEDIATE)
        self.assertTrue(result["sensitive"])


class StructuralAngerTests(unittest.TestCase):
    """Anger expressed with punctuation and capitals, not words."""

    def test_triple_exclamation_escalates_without_any_angry_word(self):
        result = _c("Where is my stuff!!!")
        self.assertGreaterEqual(_RANK[result["priority"]], _RANK[HIGH])
        self.assertIn("!!!", result["matched"])

    def test_one_or_two_exclamations_do_not_escalate(self):
        for message in ["Thanks so much!", "Love it!!"]:
            with self.subTest(message=message):
                self.assertEqual(_c(message)["priority"], NORMAL)

    def test_shouting_escalates(self):
        result = _c("WHY HAS NOBODY ANSWERED ME PLEASE REPLY TODAY")
        self.assertGreaterEqual(_RANK[result["priority"]], _RANK[HIGH])
        self.assertIn("ALL CAPS", result["matched"])

    def test_shipping_acronyms_are_not_shouting(self):
        result = _c("Do you ship via USPS UPS DHL FEDEX to the USA and is VAT included?")
        self.assertEqual(result["priority"], NORMAL)

    def test_all_caps_subject_alone_is_not_shouting(self):
        # Gorgias subjects are often machine-generated in capitals. If the caps
        # rule read the subject, every one of these would escalate.
        result = _c(
            "Hi, when will my order ship? Thanks.",
            subject="ORDER CONFIRMATION FROM BUTTONS BEBE ONLINE STORE",
        )
        self.assertEqual(result["priority"], NORMAL)

    def test_one_capitalised_acronym_mid_sentence_is_not_shouting(self):
        self.assertEqual(_c("Can I pay COD or do you need a PIN?")["priority"], NORMAL)


class NoFalsePositiveTests(unittest.TestCase):
    """Word-boundary guards — these must all stay NORMAL."""

    BENIGN = [
        "I took a trip to the store and loved it.",
        "Do you have a good grip strap for strollers?",
        "Please discard the old invoice, the new one is right.",
        "I scanned the QR code on the package.",
        "It arrived today and I love it, thank you!",
        "Do you ship to Canada and how much?",
        "What size bodysuit should I order for a 4 month old?",
        "What brands do you carry?",
        "Thanks so much, the dress is adorable!",
        "Can I pick up locally instead of coming by post?",
    ]

    def test_benign_messages_stay_normal(self):
        for message in self.BENIGN:
            with self.subTest(message=message):
                result = _c(message)
                self.assertEqual(result["priority"], NORMAL, msg=result["reason"])
                self.assertFalse(result["sensitive"])
                self.assertEqual(result["matched"], [])
                self.assertFalse(result["should_notify_owner"])


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
