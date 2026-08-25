"""Gorgias API client — fetch ticket + message data using Basic Auth."""

from __future__ import annotations

import asyncio
import html
from typing import Any
from urllib.parse import urlsplit

import httpx

from .config import get_settings
from .logging_utils import get_logger, log_event

logger = get_logger(__name__)

# ── Constants ──────────────────────────────────────────────
_API_VERSION = "/api"
_TIMEOUT = 15.0  # seconds
_USER_AGENT = "ButtonsBebe-Dashboard/1.0"
_MAX_429_RETRIES = 2
_DELIVERY_POLLS = 4
_DELIVERY_POLL_DELAY = 0.5


def _retry_after(response: httpx.Response) -> float:
    """Return a bounded delay for Gorgias rate-limit responses."""
    try:
        value = float(response.headers.get("Retry-After", "1"))
    except (TypeError, ValueError):
        value = 1.0
    return max(0.0, min(value, 10.0))


def _address(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("address") or value.get("email") or "").strip()
    return str(value or "").strip()


class GorgiasClient:
    """Thin async wrapper around the Gorgias REST API."""

    def __init__(
        self,
        subdomain: str | None = None,
        email: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
    ):
        settings = get_settings()
        self.subdomain = subdomain or settings.gorgias_subdomain
        self.email = email or settings.gorgias_api_email
        self.api_key = api_key or settings.gorgias_api_key
        self.base_url = (base_url or settings.gorgias_base_url).rstrip("/")
        self._auth = (self.email, self.api_key) if self.email and self.api_key else None
        if settings.demo_mode:
            try:
                parsed = urlsplit(self.base_url)
                local_demo = (
                    parsed.scheme == "http"
                    and parsed.hostname in {"127.0.0.1", "localhost", "::1"}
                    and parsed.port == 8190
                    and parsed.username is None
                    and parsed.password is None
                    and not parsed.path.rstrip("/")
                )
            except (TypeError, ValueError):
                local_demo = False
            if not local_demo:
                logger.error("Demo Gorgias request blocked: base URL is not localhost:8190")
                self._auth = None

    # ── Public methods ─────────────────────────────────────

    async def get_ticket(self, ticket_id: int) -> dict[str, Any] | None:
        """Fetch a full ticket with all messages and customer info."""
        if not self._auth:
            log_event(logger, "ERROR", "Gorgias credentials not configured")
            return None

        url = f"{self.base_url}{_API_VERSION}/tickets/{ticket_id}"
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.get(
                    url,
                    auth=self._auth,
                    headers={"User-Agent": _USER_AGENT, "Accept": "application/json"},
                )

                if resp.status_code == 401:
                    log_event(logger, "ERROR", "Gorgias auth failed — check API key",
                              ticket_id=ticket_id)
                    return None
                if resp.status_code == 404:
                    log_event(logger, "WARNING", "Ticket not found",
                              ticket_id=ticket_id)
                    return None
                resp.raise_for_status()
                return resp.json()

        except httpx.HTTPStatusError as exc:
            log_event(logger, "ERROR", f"Gorgias API error {exc.response.status_code}",
                      ticket_id=ticket_id)
            return None
        except httpx.RequestError as exc:
            log_event(logger, "ERROR", f"Gorgias request failed: {exc}",
                      ticket_id=ticket_id)
            return None

    async def get_message(self, message_id: int) -> dict[str, Any] | None:
        """Fetch a single message by ID."""
        if not self._auth:
            return None

        url = f"{self.base_url}{_API_VERSION}/messages/{message_id}"

        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.get(
                    url,
                    auth=self._auth,
                    headers={"User-Agent": _USER_AGENT, "Accept": "application/json"},
                )
                if resp.status_code in (401, 404):
                    log_event(logger, "WARNING", f"Message {message_id} not found")
                    return None
                resp.raise_for_status()
                return resp.json()

        except (httpx.HTTPStatusError, httpx.RequestError) as exc:
            log_event(logger, "ERROR", f"Failed to fetch message {message_id}: {exc}")
            return None

    async def get_customer(self, customer_id: int) -> dict[str, Any] | None:
        """Fetch customer details."""
        if not self._auth:
            return None

        url = f"{self.base_url}{_API_VERSION}/customers/{customer_id}"

        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.get(
                    url,
                    auth=self._auth,
                    headers={"User-Agent": _USER_AGENT, "Accept": "application/json"},
                )
                if resp.status_code in (401, 404):
                    return None
                resp.raise_for_status()
                return resp.json()
        except (httpx.HTTPStatusError, httpx.RequestError):
            return None

    async def test_connection(self) -> bool:
        """Quick connectivity test — returns True if auth works."""
        if not self._auth:
            return False

        url = f"{self.base_url}{_API_VERSION}/tickets"

        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.get(
                    url,
                    auth=self._auth,
                    params={"limit": 1},
                    headers={"User-Agent": _USER_AGENT, "Accept": "application/json"},
                )
                ok = resp.status_code == 200
                log_event(logger, "INFO", f"Gorgias connection test: {'OK' if ok else 'FAIL'}",
                          status_code=resp.status_code)
                return ok
        except Exception as exc:
            log_event(logger, "ERROR", f"Gorgias connection test failed: {exc}")
            return False

    # ── WRITE side (added for reply-from-dashboard) ────────

    async def _post_message(self, ticket_id: int, payload: dict) -> dict:
        """Low-level POST of a message to a ticket. Returns {ok, ...}."""
        if not self._auth:
            return {"ok": False, "error": "gorgias credentials not configured"}
        url = f"{self.base_url}{_API_VERSION}/tickets/{ticket_id}/messages"
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = None
                for attempt in range(_MAX_429_RETRIES + 1):
                    resp = await client.post(
                        url,
                        auth=self._auth,
                        json=payload,
                        headers={"User-Agent": _USER_AGENT, "Accept": "application/json"},
                    )
                    if resp.status_code != 429 or attempt >= _MAX_429_RETRIES:
                        break
                    await asyncio.sleep(_retry_after(resp))
                assert resp is not None
                if resp.status_code in (200, 201):
                    return {"ok": True, "message": resp.json()}
                if resp.status_code == 400 and "body_text" in payload:
                    p2 = dict(payload)
                    txt = p2.pop("body_text")
                    p2["body_html"] = txt.replace("\n", "<br>")
                    resp2 = await client.post(
                        url,
                        auth=self._auth,
                        json=p2,
                        headers={"User-Agent": _USER_AGENT, "Accept": "application/json"},
                    )
                    if resp2.status_code in (200, 201):
                        return {"ok": True, "message": resp2.json()}
                    return {"ok": False, "error": f"gorgias {resp2.status_code}: {resp2.text[:300]}"}
                return {"ok": False, "error": f"gorgias {resp.status_code}: {resp.text[:300]}"}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    async def post_internal_note(self, ticket_id: int, body_text: str) -> dict:
        """Post a staff-only internal note (not sent to the customer)."""
        payload = {
            "channel": "internal-note",
            "via": "api",
            "from_agent": True,
            "body_text": body_text,
            "public": False,
            "sender": {"email": self.email},
        }
        return await self._post_message(ticket_id, payload)

    async def send_public_reply(self, ticket_id: int, body_text: str) -> dict:
        """Send a customer-facing reply on the ticket's own channel.

        Mirrors the most recent customer message's channel + source (swapping
        direction) so the reply goes back the same way they contacted us.
        Leaves ticket status unchanged (stays open).
        """
        if not self._auth:
            return {"ok": False, "error": "gorgias credentials not configured"}
        murl = f"{self.base_url}{_API_VERSION}/messages"
        msgs = []
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as _c:
                mr = None
                for attempt in range(_MAX_429_RETRIES + 1):
                    mr = await _c.get(
                        murl,
                        auth=self._auth,
                        params={
                            "ticket_id": ticket_id,
                            "limit": 30,
                            "order_by": "created_datetime:desc",
                        },
                        headers={"User-Agent": _USER_AGENT, "Accept": "application/json"},
                    )
                    if mr.status_code != 429 or attempt >= _MAX_429_RETRIES:
                        break
                    await asyncio.sleep(_retry_after(mr))
                assert mr is not None
                if mr.status_code == 404:
                    return {"ok": False, "error": "ticket not found"}
                if mr.status_code != 200:
                    return {"ok": False, "error": f"gorgias {mr.status_code}: {mr.text[:300]}"}
                jd = mr.json()
                msgs = jd.get("data", jd) if isinstance(jd, dict) else jd
        except Exception as exc:
            return {"ok": False, "error": f"failed to read ticket: {exc}"}
        if not isinstance(msgs, list):
            msgs = []
        def _dt(m):
            return m.get("created_datetime") or m.get("sent_datetime") or ""
        msgs_sorted = sorted(msgs, key=_dt)
        base = None
        for m in reversed(msgs_sorted):
            if not m.get("from_agent", False):
                base = m
                break
        if base is None:
            return {"ok": False, "error": "no customer message available for reply routing"}
        channel = str(base.get("channel") or "").strip()
        if not channel:
            return {"ok": False, "error": "customer message has no reply channel"}
        src = base.get("source") or {}
        cust_from = src.get("from") or base.get("sender") or {}
        our_to = src.get("to") or []
        if isinstance(our_to, dict):
            our_to = [our_to]
        customer_email = _address(cust_from)
        if not customer_email:
            return {"ok": False, "error": "customer message has no recipient address"}
        source_from = our_to[0] if isinstance(our_to, list) and our_to else {}
        source_from_address = _address(source_from)
        if not source_from_address:
            return {"ok": False, "error": "customer message has no support mailbox route"}
        new_source = {}
        stype = src.get("type") or channel
        if stype:
            new_source["type"] = stype
        if cust_from:
            new_source["to"] = [{"address": customer_email}]
        new_source["from"] = {"address": source_from_address}
        payload = {
            "channel": channel,
            "via": "api",
            "from_agent": True,
            "public": True,
            "body_text": body_text,
            "body_html": html.escape(body_text).replace("\n", "<br>"),
            "sender": {"email": self.email},
            "receiver": {"email": customer_email},
            "source": new_source,
        }
        result = await self._post_message(ticket_id, payload)
        if not result.get("ok"):
            return result
        created = result.get("message") or {}
        message_id = created.get("id")
        if not message_id:
            return {"ok": False, "error": "Gorgias did not return a message id"}
        delivery = await self._wait_for_delivery(ticket_id, int(message_id))
        return {
            "ok": delivery["status"] != "failed",
            "delivery_status": delivery["status"],
            "message_id": int(message_id),
            "message": delivery.get("message", created),
            **({"error": delivery["error"]} if delivery.get("error") else {}),
        }

    async def _wait_for_delivery(self, ticket_id: int, message_id: int) -> dict:
        """Poll the documented message resource until sent, failed, or pending."""
        url = f"{self.base_url}{_API_VERSION}/tickets/{ticket_id}/messages/{message_id}"
        latest: dict[str, Any] = {}
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                for attempt in range(_DELIVERY_POLLS):
                    resp = await client.get(
                        url,
                        auth=self._auth,
                        headers={"User-Agent": _USER_AGENT, "Accept": "application/json"},
                    )
                    if resp.status_code == 200:
                        latest = resp.json()
                        if latest.get("sent_datetime"):
                            return {"status": "sent", "message": latest}
                        if latest.get("failed_datetime") or latest.get("last_sending_error"):
                            error = latest.get("last_sending_error") or "Gorgias failed to deliver the message"
                            return {"status": "failed", "message": latest, "error": str(error)}
                    elif resp.status_code == 429 and attempt < _DELIVERY_POLLS - 1:
                        await asyncio.sleep(_retry_after(resp))
                        continue
                    elif resp.status_code in (401, 403, 404):
                        return {"status": "unknown", "error": f"could not verify Gorgias message ({resp.status_code})"}
                    if attempt < _DELIVERY_POLLS - 1:
                        await asyncio.sleep(_DELIVERY_POLL_DELAY)
        except Exception as exc:
            return {"status": "unknown", "error": f"could not verify Gorgias delivery: {exc}"}
        return {"status": "pending", "message": latest}
