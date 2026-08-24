from __future__ import annotations

import unittest
from pathlib import Path
import sys
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from shopify import shopify  # noqa: E402


class TestShopifyGraphQLReadOnly(unittest.TestCase):
    def test_mutation_is_rejected_before_headers_token_or_request(self) -> None:
        mutation = """
            # The operation name and whitespace must not affect the guard.
            mutation UpdateProduct {
                productUpdate(product: {id: \"gid://shopify/Product/1\"}) {
                    product { id }
                }
            }
        """
        with patch.object(shopify, "_headers") as headers, patch.object(
            shopify, "_get_token"
        ) as get_token, patch.object(shopify.requests, "post") as post:
            with self.assertRaisesRegex(ValueError, "only GraphQL query"):
                shopify._graphql(mutation)

        headers.assert_not_called()
        get_token.assert_not_called()
        post.assert_not_called()

    def test_only_query_operations_are_allowed(self) -> None:
        with patch.object(shopify, "_headers") as headers, patch.object(
            shopify.requests, "post"
        ) as post:
            with self.assertRaisesRegex(ValueError, "only GraphQL query"):
                shopify._graphql("subscription Live { products { edges { node { id } } } }")
        headers.assert_not_called()
        post.assert_not_called()

    def test_named_query_with_comments_and_strings_is_forwarded(self) -> None:
        response = Mock()
        response.json.return_value = {"data": {"shop": {"name": "Buttons Bebe"}}}
        query = """
            # A word that must stay inside a comment.
            query ShopName($search: String!) {
                shop {
                    name
                    description(search: $search, note: "mutation")
                }
            }
        """
        with patch.object(shopify, "_base_url", return_value="https://shop.myshopify.com/admin/api/2024-01"):
            with patch.object(shopify, "_headers", return_value={"X-Test": "1"}) as headers:
                with patch.object(shopify.requests, "post", return_value=response) as post:
                    result = shopify._graphql(query, {"search": "dress"})

        self.assertEqual(result, {"shop": {"name": "Buttons Bebe"}})
        headers.assert_called_once_with()
        post.assert_called_once()


if __name__ == "__main__":
    unittest.main()
