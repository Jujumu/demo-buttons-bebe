from __future__ import annotations

import unittest

from fake_kb_mcp import load_fixture, search_fixture


class FakeKnowledgeBaseTests(unittest.TestCase):
    def test_fixture_is_demo_only_and_has_expected_documents(self):
        documents = load_fixture()
        self.assertGreaterEqual(len(documents), 8)
        self.assertTrue(all("client" not in document["text"].lower() for document in documents))
        self.assertTrue(any(document["sensitive"] for document in documents))

    def test_shipping_query_returns_shipping_guidance(self):
        results = search_fixture("where is my order and when will it arrive", k=3)
        self.assertTrue(results)
        self.assertTrue(any("shipping" in result["file"] + result["title"].lower()
                            or "ship" in result["file"] + result["title"].lower()
                            for result in results))
        self.assertIn("score", results[0])
        self.assertIn("sensitive", results[0])

    def test_refund_query_preserves_sensitive_flag(self):
        results = search_fixture("I want a refund", k=5)
        self.assertTrue(results)
        self.assertTrue(any(result["sensitive"] for result in results))

    def test_result_count_is_bounded_and_non_mutating(self):
        documents = load_fixture()
        original_count = len(documents)
        self.assertEqual(search_fixture("tracking", k=0), [])
        self.assertLessEqual(len(search_fixture("tracking", k=2)), 2)
        self.assertEqual(len(documents), original_count)


if __name__ == "__main__":
    unittest.main()
