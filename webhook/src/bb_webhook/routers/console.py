"""Human-gated console actions and feedback review endpoints."""

from __future__ import annotations

import asyncio as _asyncio
import os as _os

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from .. import deps
from ..gorgias_client import GorgiasClient as _GClient
from ..learning import ledger as _ledger, record_lesson as _record_lesson
from ..logging_utils import get_logger, log_event

try:
    # Optional at import time: review routes must not prevent the webhook
    # receiver from starting when the feedback package is not installed.
    from feedback import review as _review
except Exception:  # pragma: no cover - depends on deployment packaging
    _review = None

router = APIRouter(prefix="/dashboard/api")
logger = get_logger(__name__)

_HERMES_BIN = _os.environ.get("HERMES_BIN", "/usr/local/bin/hermes")
_HERMES_HOME = _os.environ.get("HERMES_OS_HOME", "/root")
_HERMES_PROFILE = _os.environ.get("HERMES_PROFILE", "").strip()
_HERMES_REWRITE_TOOLSETS = _os.environ.get("HERMES_REWRITE_TOOLSETS", "todo").strip()
_HERMES_IGNORE_RULES = _os.environ.get("HERMES_IGNORE_RULES", "").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
_SUPPORT_STORE_NAME = " ".join(
    _os.environ.get("SUPPORT_STORE_NAME", "Buttons Bebe").split()
)[:80] or "Buttons Bebe"


def _app_value(name: str, default):
    return deps.resolve(name, default)


def _review_unavailable() -> JSONResponse:
    return JSONResponse(status_code=503, content={"error": "review_unavailable"})


@router.get("/review/list")
async def review_list() -> JSONResponse:
    if _review is None:
        return _review_unavailable()
    return JSONResponse(content={"pending": _review.list_pending()})


@router.get("/review/packet/{ticket_id}")
async def review_packet(ticket_id: str) -> JSONResponse:
    if _review is None:
        return _review_unavailable()
    packet = _review.get_packet(ticket_id)
    if not packet:
        return JSONResponse(status_code=404, content={"error": "not_found"})
    return JSONResponse(
        content={
            "ticket_id": packet["ticket_id"],
            "front": packet["front"],
            "situation_masked": packet["situation_masked"],
            "reply_masked": packet["reply_masked"],
            "reply_raw": packet["reply"],
            "pii_reply": packet["pii_reply"],
        }
    )


@router.post("/review/approve/{ticket_id}")
async def review_approve(ticket_id: str, request: Request) -> JSONResponse:
    if _review is None:
        return _review_unavailable()
    try:
        body = await request.json()
    except Exception:
        body = {}
    result = _review.approve(
        ticket_id,
        pii_cleared=bool(body.get("pii_cleared")),
        note=str(body.get("note", "")),
        why=str(body.get("why", "")),
    )
    return JSONResponse(content=result, status_code=200 if result.get("ok") else 400)


@router.post("/review/reject/{ticket_id}")
async def review_reject(ticket_id: str, purge: bool = False) -> JSONResponse:
    if _review is None:
        return _review_unavailable()
    return JSONResponse(content=_review.reject(ticket_id, purge=purge))


@router.post("/review/reindex")
async def review_reindex() -> JSONResponse:
    if _review is None:
        return _review_unavailable()
    return JSONResponse(content=_review.reindex())


@router.post("/ticket/{ticket_id}/send")
async def action_send(ticket_id: int, request: Request) -> JSONResponse:
    """Send a customer-facing reply after an explicit human confirmation."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"error": "invalid_json"})
    if not isinstance(body, dict):
        return JSONResponse(status_code=400, content={"error": "invalid_json_object"})
    if not await deps.database_function("dashboard_ticket_exists")(ticket_id):
        return JSONResponse(status_code=404, content={"error": "ticket_not_in_console"})
    raw_text = body.get("text", "")
    if not isinstance(raw_text, str):
        return JSONResponse(status_code=400, content={"error": "invalid_reply"})
    text = raw_text.strip()
    if not text or len(text) > 50_000:
        return JSONResponse(status_code=400, content={"error": "empty reply"})
    if body.get("confirmed") is not True:
        return JSONResponse(status_code=409, content={"error": "confirmation_required"})
    result = await _app_value("_GClient", _GClient)().send_public_reply(ticket_id, text)
    if not result.get("ok"):
        log_event(
            logger,
            "ERROR",
            "Public reply failed",
            ticket_id=ticket_id,
            detail=result.get("error"),
            message_id=result.get("message_id"),
            delivery_status=result.get("delivery_status"),
        )
        return JSONResponse(
            status_code=502,
            content={
                "error": result.get("error", "send failed"),
                "delivery_status": result.get("delivery_status", "failed"),
                **({"message_id": result["message_id"]} if result.get("message_id") else {}),
            },
        )
    delivery_status = result.get("delivery_status", "unknown")
    if delivery_status == "sent":
        log_event(
            logger,
            "INFO",
            "Public reply sent from dashboard",
            ticket_id=ticket_id,
            message_id=result.get("message_id"),
            delivery_status=delivery_status,
        )
    else:
        log_event(
            logger,
            "WARNING",
            "Public reply accepted by Gorgias; delivery is not confirmed",
            ticket_id=ticket_id,
            message_id=result.get("message_id"),
            delivery_status=delivery_status,
        )
    try:
        _app_value("_record_lesson", _record_lesson)(
            "sent",
            ticket_id,
            str(body.get("message_text", "")),
            str(body.get("ai_draft", "")),
            text,
            customer_name=str(body.get("customer_name", "")),
        )
    except Exception:
        pass
    return JSONResponse(
        status_code=200 if delivery_status == "sent" else 202,
        content={
            "ok": True,
            "delivery_status": delivery_status,
            **({"message_id": result["message_id"]} if result.get("message_id") else {}),
        },
    )


@router.post("/ticket/{ticket_id}/note")
async def action_note(ticket_id: int, request: Request) -> JSONResponse:
    """Post a draft as a staff-only Gorgias internal note."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"error": "invalid_json"})
    if not isinstance(body, dict):
        return JSONResponse(status_code=400, content={"error": "invalid_json_object"})
    if not await deps.database_function("dashboard_ticket_exists")(ticket_id):
        return JSONResponse(status_code=404, content={"error": "ticket_not_in_console"})
    raw_text = body.get("text", "")
    if not isinstance(raw_text, str):
        return JSONResponse(status_code=400, content={"error": "invalid_note"})
    text = raw_text.strip()
    if not text or len(text) > 50_000:
        return JSONResponse(status_code=400, content={"error": "empty note"})
    result = await _app_value("_GClient", _GClient)().post_internal_note(ticket_id, text)
    if not result.get("ok"):
        log_event(
            logger,
            "ERROR",
            "Internal note failed",
            ticket_id=ticket_id,
            detail=result.get("error"),
        )
        return JSONResponse(
            status_code=502,
            content={"error": result.get("error", "note failed")},
        )
    log_event(logger, "INFO", "Internal note posted from dashboard", ticket_id=ticket_id)
    try:
        _app_value("_record_lesson", _record_lesson)(
            "note",
            ticket_id,
            str(body.get("message_text", "")),
            str(body.get("ai_draft", "")),
            text,
            customer_name=str(body.get("customer_name", "")),
        )
    except Exception:
        pass
    return JSONResponse(content={"ok": True})


@router.post("/ticket/{ticket_id}/rewrite")
async def action_rewrite(ticket_id: int, request: Request) -> JSONResponse:
    """Rewrite a draft through Hermes; this route never sends it."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"error": "invalid_json"})
    if not isinstance(body, dict):
        return JSONResponse(status_code=400, content={"error": "invalid_json_object"})
    if not await deps.database_function("dashboard_ticket_exists")(ticket_id):
        return JSONResponse(status_code=404, content={"error": "ticket_not_in_console"})
    for field in ("draft", "instruction", "message_text", "customer_name"):
        if field in body and not isinstance(body[field], str):
            return JSONResponse(status_code=400, content={"error": f"invalid_{field}"})
    draft = body.get("draft", "").strip()
    instruction = body.get("instruction", "").strip()
    customer_msg = body.get("message_text", "").strip()
    if not instruction:
        return JSONResponse(status_code=400, content={"error": "no instruction"})
    if max(len(draft), len(instruction), len(customer_msg)) > 50_000:
        return JSONResponse(status_code=413, content={"error": "rewrite_input_too_large"})

    store_name = _app_value("_SUPPORT_STORE_NAME", _SUPPORT_STORE_NAME)
    prompt = (
        f"You are rewriting a customer-support reply for {store_name}. "
        "Output ONLY the final customer-facing reply "
        "text - no preamble, no quotes, no commentary, no sign-off notes.\n\n"
        "CUSTOMER MESSAGE:\n" + customer_msg + "\n\n"
        "CURRENT DRAFT REPLY:\n" + draft + "\n\n"
        "REWRITE INSTRUCTION FROM THE HUMAN AGENT:\n" + instruction + "\n\n"
        f"Rewrite the reply to follow the instruction. Stay accurate to "
        f"{store_name} policy; do not invent facts, prices, or promises."
    )
    asyncio_module = _app_value("_asyncio", _asyncio)
    try:
        env = dict(_os.environ)
        env["HOME"] = _app_value("_HERMES_HOME", _HERMES_HOME)
        command = [_app_value("_HERMES_BIN", _HERMES_BIN)]
        profile = _app_value("_HERMES_PROFILE", _HERMES_PROFILE)
        if profile:
            command.extend(["-p", profile])
        if _app_value("_HERMES_IGNORE_RULES", _HERMES_IGNORE_RULES):
            command.append("--ignore-rules")
        toolsets = _app_value("_HERMES_REWRITE_TOOLSETS", _HERMES_REWRITE_TOOLSETS)
        if toolsets:
            command.extend(["-t", toolsets])
        command.extend(["-z", prompt])
        process = await asyncio_module.create_subprocess_exec(
            *command,
            stdout=asyncio_module.subprocess.PIPE,
            stderr=asyncio_module.subprocess.PIPE,
            env=env,
        )
        output, _error = await asyncio_module.wait_for(process.communicate(), timeout=150)
    except asyncio_module.TimeoutError:
        return JSONResponse(status_code=504, content={"error": "rewrite timed out"})
    except Exception as exc:
        return JSONResponse(status_code=500, content={"error": str(exc)})

    reply = (output or b"").decode("utf-8", "ignore").strip()
    if not reply:
        return JSONResponse(status_code=502, content={"error": "empty rewrite"})
    for marker in [
        "\nThe response above",
        "\nThe previous response",
        "\nThe reply above",
        "\nNote:",
        "\nNote that",
        "\nI have rewritten",
        "\n(Note",
        "\nLet me know",
    ]:
        marker_index = reply.find(marker)
        if marker_index != -1:
            reply = reply[:marker_index].strip()
    try:
        _app_value("_record_lesson", _record_lesson)(
            "rewrite",
            ticket_id,
            customer_msg,
            draft,
            reply,
            instruction=instruction,
            customer_name=str(body.get("customer_name", "")),
        )
    except Exception:
        pass
    return JSONResponse(content={"ok": True, "draft": reply})


@router.get("/learning")
async def learning_stats() -> JSONResponse:
    """Return the learning ledger used by the console."""
    return JSONResponse(content=_app_value("_ledger", _ledger)())
