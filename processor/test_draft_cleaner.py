"""Unit tests for processor/draft_cleaner.py.

Ported from fable/tests/unit/test_draft_cleaner.py and converted from pytest to
unittest so the offline release gate (tools/verify_release.sh) can run it.

Where possible the cases are seeded with the REAL model outputs from the live QA
run (testing/results-live.json), so the leak fixes are exercised against genuine
drafts rather than toy strings:

  * QA #01 (R01, WISMO), #04 (R04, intl + return), #10 (R10, fabric) — the model
    sometimes repeats the whole draft twice or appends self-commentary
    ("The response above was complete...").
  * QA #19 (E01, empty message) — nothing to answer, must NOT draft.

Those seeded cases skip themselves if testing/ has not been merged yet (Task 1 of
the Fable port). Everything else runs unconditionally.

The other half of the suite proves the cleaner does NOT touch clean drafts: a
normal reply that happens to say "complete" or "note" mid-sentence is left
untouched, and a legitimate escalation internal note is not cut.
"""

from __future__ import annotations

import json
import pathlib
import re
import sys
import unittest

PROCESSOR_DIR = pathlib.Path(__file__).resolve().parent
if str(PROCESSOR_DIR) not in sys.path:
    sys.path.insert(0, str(PROCESSOR_DIR))

import draft_cleaner as dc  # noqa: E402

RESULTS_LIVE = PROCESSOR_DIR.parent / "testing" / "results-live.json"
_HAVE_LIVE = RESULTS_LIVE.is_file()
_SKIP_REASON = f"{RESULTS_LIVE} not present — merge the Task 1 test harness first"

_GOOD = "Hi! Thanks for reaching out. Your order usually ships within 24-48 hours."
REAL_DRAFT_IDS = ["R01", "R04", "R10"]

SELF_TALK_LINES = [
    ("response-above", "The response above was complete and answers the question."),
    ("previous-complete", "The previous response was already complete."),
    ("prior-complete", "The prior draft is complete."),
    ("above-response", "The above response addresses the customer's question."),
    ("this-reply-complete", "This reply is complete."),
    ("this-response-above", "This response above is now complete."),
    ("i-have-completed", "I have completed the response."),
    ("i-have-finished", "I have now finished this draft."),
    ("note-to-reviewer", "Note to the reviewer: double-check the tone before sending."),
    ("note-to-team", "Note to team: this looks right."),
    ("end-of-response", "End of response"),
    ("end-of-draft-bracket", "[End of draft]"),
    ("as-an-ai", "As an AI, I cannot process the refund myself."),
]


def _norm(s: str) -> str:
    """Whitespace-flatten + lowercase (mirrors the cleaner's own normalisation)."""
    return re.sub(r"\s+", " ", s or "").strip().lower()


def _answer_body(hermes_output: str) -> str:
    """Pull just the drafted reply out of a `RISK/ACTION/ANSWER:` block."""
    marker = "ANSWER:\n"
    i = hermes_output.find(marker)
    return (hermes_output[i + len(marker):] if i != -1 else hermes_output).strip()


def _live_answer(ticket_id: str) -> str:
    data = json.loads(RESULTS_LIVE.read_text(encoding="utf-8"))
    for row in data:
        if row.get("id") == ticket_id:
            return _answer_body(row["hermes_output"])
    raise KeyError(f"{ticket_id} not found in {RESULTS_LIVE}")


# ===========================================================================
# 1. Self-talk markers — each one is stripped from the tail of a draft.
# ===========================================================================
class SelfTalkTests(unittest.TestCase):
    def test_each_self_talk_marker_is_stripped(self):
        for label, marker in SELF_TALK_LINES:
            with self.subTest(marker=label):
                draft = f"{_GOOD}\n\n{marker}\n\nSome trailing model chatter."
                res = dc.clean_draft(draft)
                self.assertFalse(res.no_draft)
                self.assertIn("stripped model self-commentary", res.reasons)
                self.assertEqual(res.text, _GOOD)
                self.assertNotIn(marker, res.text)

    def test_marker_with_leading_markdown_is_stripped(self):
        res = dc.clean_draft(f"{_GOOD}\n\n> The response above was complete.")
        self.assertEqual(res.text, _GOOD)
        self.assertIn("stripped model self-commentary", res.reasons)

    def test_draft_that_is_only_self_talk_becomes_no_draft(self):
        res = dc.clean_draft("The response above was complete.")
        self.assertTrue(res.no_draft)
        self.assertEqual(res.text, "")
        self.assertIn("nothing left after cleaning", res.reasons)


# ===========================================================================
# 2. Duplicated-draft cases — whole-text and paragraph-level.
# ===========================================================================
class DuplicationTests(unittest.TestCase):
    def test_whole_text_duplicated_blank_line(self):
        res = dc.clean_draft(f"{_GOOD}\n\n{_GOOD}")
        self.assertIn("removed duplicated draft body", res.reasons)
        self.assertEqual(res.text, _GOOD)

    def test_whole_text_duplicated_single_newline(self):
        res = dc.clean_draft(f"{_GOOD}\n{_GOOD}")
        self.assertIn("removed duplicated draft body", res.reasons)
        self.assertEqual(_norm(res.text), _norm(_GOOD))

    def test_whole_text_tripled(self):
        res = dc.clean_draft(f"{_GOOD}\n\n{_GOOD}\n\n{_GOOD}")
        self.assertIn("removed duplicated draft body", res.reasons)
        self.assertEqual(_norm(res.text), _norm(_GOOD))

    def test_paragraph_level_duplication_multi_paragraph(self):
        body = (
            "Hi there,\n\n"
            "Thanks for reaching out about your order. It usually ships in 24-48 hours "
            "before it leaves our warehouse.\n\n"
            "Warmly,\nButtons Bebe Support"
        )
        res = dc.clean_draft(f"{body}\n\n{body}")
        self.assertIn("removed duplicated draft body", res.reasons)
        self.assertEqual(res.text, body)
        self.assertEqual(res.text.count("Buttons Bebe Support"), 1)

    def test_dedup_recovers_original_formatting_exactly(self):
        body = "Line one of the reply here.\n\n- bullet a\n- bullet b\n\nThanks so much!"
        res = dc.clean_draft(f"{body}\n\n{body}")
        self.assertEqual(res.text, body)


# ===========================================================================
# 3. Seeded with REAL leaked-style drafts from testing/results-live.json.
# ===========================================================================
@unittest.skipUnless(_HAVE_LIVE, _SKIP_REASON)
class RealDraftTests(unittest.TestCase):
    def test_real_answer_duplicated_is_collapsed(self):
        for ticket_id in REAL_DRAFT_IDS:
            with self.subTest(ticket=ticket_id):
                answer = _live_answer(ticket_id)
                self.assertGreater(len(answer), 40)
                res = dc.clean_draft(f"{answer}\n\n{answer}")
                self.assertFalse(res.no_draft)
                self.assertIn("removed duplicated draft body", res.reasons)
                self.assertEqual(_norm(res.text), _norm(answer))
                self.assertLess(len(res.text), len(answer) * 1.2)

    def test_real_answer_with_appended_self_talk_is_trimmed(self):
        for ticket_id in REAL_DRAFT_IDS:
            with self.subTest(ticket=ticket_id):
                answer = _live_answer(ticket_id)
                leaked = f"{answer}\n\nThe response above was complete and ready for review."
                res = dc.clean_draft(leaked)
                self.assertIn("stripped model self-commentary", res.reasons)
                self.assertEqual(_norm(res.text), _norm(answer))

    def test_real_answer_duplicated_then_self_talk(self):
        answer = _live_answer("R01")
        leaked = f"{answer}\n\n{answer}\n\nThe response above was complete."
        res = dc.clean_draft(leaked)
        self.assertIn("stripped model self-commentary", res.reasons)
        self.assertIn("removed duplicated draft body", res.reasons)
        self.assertEqual(_norm(res.text), _norm(answer))

    def test_real_clean_answer_passes_through_untouched(self):
        for ticket_id in REAL_DRAFT_IDS:
            with self.subTest(ticket=ticket_id):
                answer = _live_answer(ticket_id)
                res = dc.clean_draft(answer)
                self.assertFalse(res.no_draft)
                self.assertEqual(res.reasons, [])
                self.assertEqual(res.text, answer)

    def test_empty_customer_message_qa19(self):
        rows = json.loads(RESULTS_LIVE.read_text(encoding="utf-8"))
        e01 = next(r for r in rows if r["id"] == "E01")
        self.assertEqual(e01["message"], "")
        self.assertFalse(dc.should_draft(e01["message"]).ok)


# ===========================================================================
# 4. No false positives — clean drafts pass through UNCHANGED.
# ===========================================================================
class NoFalsePositiveTests(unittest.TestCase):
    def test_clean_reply_saying_complete_is_not_cut(self):
        draft = "Hi! Your order is complete and on its way. Thanks so much for your patience!"
        res = dc.clean_draft(draft)
        self.assertEqual(res.text, draft)
        self.assertEqual(res.reasons, [])

    def test_clean_reply_saying_note_is_not_cut(self):
        draft = "Hi! Note that processing takes 24-48 hours before your order ships. Thanks!"
        res = dc.clean_draft(draft)
        self.assertEqual(res.text, draft)
        self.assertEqual(res.reasons, [])

    def test_legitimate_escalation_internal_note_is_not_cut(self):
        note = (
            "Internal note for human review:\n"
            "Customer is requesting a refund on order #10322. Do not promise money.\n"
            "Notes for the human agent: verify the delivery date and 7-day window first."
        )
        res = dc.clean_draft(note)
        self.assertEqual(res.text, note)
        self.assertEqual(res.reasons, [])

    def test_two_different_paragraphs_are_not_deduped(self):
        draft = (
            "Hi! Yes, we ship to Canada; the rate shows at checkout.\n\n"
            "Customs and duties are the customer's responsibility. Thanks!"
        )
        res = dc.clean_draft(draft)
        self.assertEqual(res.text, draft)
        self.assertEqual(res.reasons, [])

    def test_short_repeated_content_is_not_collapsed(self):
        draft = "Yes.\n\nYes."
        res = dc.clean_draft(draft)
        self.assertEqual(res.text, draft)
        self.assertNotIn("removed duplicated draft body", res.reasons)

    def test_sensitive_prefix_draft_survives(self):
        # The console strips the [SENSITIVE ...] banner itself; the cleaner must
        # not treat the banner line as self-talk and throw the draft away.
        draft = ("[SENSITIVE — REVIEW CAREFULLY BEFORE SENDING]\n\n"
                 "Hi! We are looking into your refund request and will follow up shortly.")
        res = dc.clean_draft(draft)
        self.assertEqual(res.text, draft)
        self.assertEqual(res.reasons, [])


# ===========================================================================
# 5. Empty / whitespace drafts -> no_draft.
# ===========================================================================
class EmptyDraftTests(unittest.TestCase):
    def test_empty_or_whitespace_draft_is_no_draft(self):
        for bad in ["", "   ", "\n\n", "  \n \t ", None]:
            with self.subTest(value=repr(bad)):
                res = dc.clean_draft(bad)
                self.assertTrue(res.no_draft)
                self.assertEqual(res.text, "")

    def test_repetition_collapses_all_the_way_not_just_once(self):
        """4x used to come out doubled: the dedupe only knew 2x and 3x."""
        for copies in (2, 3, 4, 6, 8, 9):
            with self.subTest(copies=copies):
                res = dc.clean_draft("\n\n".join([_GOOD] * copies))
                self.assertEqual(_norm(res.text), _norm(_GOOD),
                                 f"{copies} copies did not collapse to one")

    def test_clean_draft_is_idempotent(self):
        leaked = f"{_GOOD}\n\n{_GOOD}\n\nThe response above was complete."
        once = dc.clean_draft(leaked).text
        twice = dc.clean_draft(once)
        self.assertEqual(twice.text, once)
        self.assertEqual(twice.reasons, [])


# ===========================================================================
# 6. should_draft — gate on the CUSTOMER message.
# ===========================================================================
class ShouldDraftTests(unittest.TestCase):
    NO_CONTENT = [
        "", "  ", "...", "thanks", "Thanks!", "Thank you!!",
        "thank you so much!", "ty", "ok", "Perfect, thanks so much!",
        "Got it, thank you!", "cheers", "Thanks again for everything!",
        "\U0001F44D", "\U0001F64F", "\U0001F44D\U0001F44D", None,
    ]
    REAL_QUESTIONS = [
        "Where is my order #BB1015?",
        "I want a refund for order #10322.",
        "Do you ship to Canada and how much?",
        "thanks, but where is my order?",
        "Can I change my shipping address?",
    ]

    def test_should_not_draft_for_no_content(self):
        for msg in self.NO_CONTENT:
            with self.subTest(message=repr(msg)):
                s = dc.should_draft(msg)
                self.assertFalse(s.ok)
                self.assertTrue(s.reason)

    def test_should_draft_for_real_questions(self):
        for msg in self.REAL_QUESTIONS:
            with self.subTest(message=msg):
                self.assertTrue(dc.should_draft(msg).ok)

    def test_sensitive_message_always_drafts(self):
        # A gate that suppressed a refund or damage complaint would be a
        # customer-facing failure. These must never be gated out.
        for msg in ["refund", "my order arrived damaged", "this is unacceptable",
                    "I want to speak to a manager"]:
            with self.subTest(message=msg):
                self.assertTrue(dc.should_draft(msg).ok)

    # ── regressions from the code review ────────────────────────────
    def test_filler_without_a_thanks_anchor_is_not_an_acknowledgement(self):
        """The original gate matched any string of filler words.

        "So much for the help!" is a customer being sarcastic, not a customer
        saying thank you. Suppressing it meant no draft AND no owner alert.
        """
        for msg in ["So much for the help!", "So much for your team.",
                    "well that is just great", "So much for all of it"]:
            with self.subTest(message=msg):
                self.assertTrue(dc.should_draft(msg).ok, msg)

    def test_a_bare_question_mark_or_angry_emoji_still_drafts(self):
        """A customer chasing a reply is not an acknowledgement."""
        for msg in ["?", "??", "?!", "!", "\U0001F621", "\U0001F92C", "\U0001F44E"]:
            with self.subTest(message=repr(msg)):
                self.assertTrue(dc.should_draft(msg).ok, repr(msg))

    def test_subject_counts_as_content(self):
        """HTML-only mail often arrives with an empty body and a real subject."""
        s = dc.should_draft("", subject="Do you have this in 6-9 months?")
        self.assertTrue(s.ok)
        s = dc.should_draft("thanks!", subject="Where is order #10322?")
        self.assertTrue(s.ok)
        # both empty is still nothing to answer
        self.assertFalse(dc.should_draft("", subject="").ok)
        # a thank-you subject with a thank-you body is still an ack
        self.assertFalse(dc.should_draft("thanks!", subject="Thank you!").ok)

    def test_gate_is_linear_not_exponential(self):
        """The original regex took >1s on 350 bytes and never returned on ~700.

        should_draft() runs synchronously before the first await, so a slow
        call freezes the whole processor - the job timeout cannot interrupt it.
        """
        import time
        payload = "Much appreciated! " * 400 + "Sent from my iPhone"
        self.assertGreater(len(payload), 7000)
        started = time.perf_counter()
        dc.should_draft(payload)
        elapsed = time.perf_counter() - started
        self.assertLess(elapsed, 0.5,
                        f"should_draft took {elapsed:.3f}s on {len(payload)} bytes")

    def test_gate_is_linear_on_a_long_hostile_message(self):
        import time
        for payload in ("thanks " * 5000, "a" * 50000, ("thank you so much " * 2000)):
            with self.subTest(length=len(payload)):
                started = time.perf_counter()
                dc.should_draft(payload)
                self.assertLess(time.perf_counter() - started, 0.5)


if __name__ == "__main__":
    unittest.main()
