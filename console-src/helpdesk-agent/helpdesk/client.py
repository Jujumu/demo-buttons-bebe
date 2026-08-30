"""Read-only Admin GraphQL client. Mutations never leave this process."""

from __future__ import annotations

import json
import re
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .auth import cached_token
from .errors import HelpdeskError, forbidden_write
from .names import API_VERSION

_OP = re.compile(r"^\s*(?:#.*\n\s*)*(query|mutation|subscription)\b", re.I)


def assert_query_only(document: str) -> None:
    match = _OP.match(document or "")
    if match and match.group(1).lower() != "query":
        raise forbidden_write()
    if re.search(r"^\s*mutation\b", document or "", re.I | re.M):
        raise forbidden_write()


def graphql(
    shop: str,
    client_id: str,
    client_secret: str,
    document: str,
    variables: dict[str, Any] | None = None,
    *,
    api_version: str = API_VERSION,
) -> dict[str, Any]:
    assert_query_only(document)
    token = cached_token(shop, client_id, client_secret)
    request = Request(
        f"https://{shop}/admin/api/{api_version}/graphql.json",
        data=json.dumps({"query": document, "variables": variables or {}}).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "X-Shopify-Access-Token": token,
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise HelpdeskError("shopify_error", "Shopify GraphQL request failed") from exc
    except (URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise HelpdeskError("shopify_error", "Shopify GraphQL request failed") from exc
    if payload.get("errors"):
        raise HelpdeskError("shopify_error", "Shopify GraphQL returned errors")
    data = payload.get("data")
    if not isinstance(data, dict):
        raise HelpdeskError("shopify_error", "Shopify GraphQL returned no data")
    return data
