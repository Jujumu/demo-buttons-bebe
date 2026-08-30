"""Dashboard read APIs and processor result ingestion."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from .. import deps

router = APIRouter(prefix="/dashboard/api")


@router.get("/messages")
async def dashboard_messages(
    limit: int = 50,
    offset: int = 0,
    customer_only: bool = False,
) -> JSONResponse:
    """Return parsed messages as JSON."""
    messages = await deps.database_function("get_parsed_messages")(
        limit=max(1, min(limit, 200)),
        offset=max(0, offset),
        customer_only=customer_only,
    )
    return JSONResponse(content=messages)


@router.get("/stats")
async def dashboard_stats() -> JSONResponse:
    """Return aggregate processing statistics plus configured store hosts."""
    stats = await deps.database_function("get_result_stats")()
    settings = deps.get_settings()
    shop = (getattr(settings, "shopify_shop", "") or "").strip()
    subdomain = (getattr(settings, "gorgias_subdomain", "") or "").strip()
    if isinstance(stats, dict):
        stats = {
            **stats,
            "shopify_shop": shop,
            "gorgias_host": f"{subdomain}.gorgias.com" if subdomain else "",
        }
    return JSONResponse(content=stats)


@router.get("/tickets")
async def dashboard_tickets_api(limit: int = 100, offset: int = 0) -> JSONResponse:
    """Return customer messages joined with AI processing results."""
    tickets = await deps.database_function("get_dashboard_tickets")(
        limit=max(1, min(limit, 500)),
        offset=max(0, offset),
    )
    return JSONResponse(content=tickets)


@router.post("/results")
async def record_result_api(request: Request) -> JSONResponse:
    """Record a Hermes result posted by the processor."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"error": "invalid_json"})
    if not isinstance(body, dict):
        return JSONResponse(status_code=400, content={"error": "invalid_json_object"})

    required = {"ticket_id", "message_id", "priority", "action"}
    if not required.issubset(body.keys()):
        return JSONResponse(
            status_code=400,
            content={"error": "missing_fields", "required": list(required)},
        )

    ticket_id = body.get("ticket_id")
    message_id_raw = body.get("message_id")
    job_id = body.get("job_id")
    priority = body.get("priority")
    action = body.get("action")
    reason = body.get("reason", "")
    draft_text = body.get("draft_text")
    if (
        not isinstance(ticket_id, int)
        or isinstance(ticket_id, bool)
        or ticket_id <= 0
        or ticket_id > 9_223_372_036_854_775_807
    ):
        return JSONResponse(status_code=400, content={"error": "invalid_ticket_id"})
    if (
        isinstance(message_id_raw, bool)
        or not isinstance(message_id_raw, (str, int))
        or not str(message_id_raw).strip()
        or len(str(message_id_raw)) > 128
    ):
        return JSONResponse(status_code=400, content={"error": "invalid_message_id"})
    if job_id is not None and (
        not isinstance(job_id, int) or isinstance(job_id, bool) or job_id <= 0
    ):
        return JSONResponse(status_code=400, content={"error": "invalid_job_id"})
    if not isinstance(priority, str) or priority not in {"critical", "high", "normal", "low"}:
        return JSONResponse(status_code=400, content={"error": "invalid_priority"})
    if not isinstance(action, str) or action not in {
        "drafted",
        "sensitive_draft",
        "escalated",
        "no_kb_match",
        "no_draft_needed",
    }:
        return JSONResponse(status_code=400, content={"error": "invalid_action"})
    if not isinstance(reason, str) or len(reason) > 2_000:
        return JSONResponse(status_code=400, content={"error": "invalid_reason"})
    if draft_text is not None and (
        not isinstance(draft_text, str) or len(draft_text) > 100_000
    ):
        return JSONResponse(status_code=400, content={"error": "invalid_draft_text"})
    for field in ("notify_owner", "gorgias_priority_set", "note_posted"):
        if field in body and not isinstance(body[field], bool):
            return JSONResponse(status_code=400, content={"error": f"invalid_{field}"})

    await deps.database_function("record_ticket_result")(
        ticket_id=ticket_id,
        message_id=str(message_id_raw),
        job_id=job_id,
        priority=priority,
        action=action,
        reason=reason,
        notify_owner=bool(body.get("notify_owner", False)),
        gorgias_priority_set=bool(body.get("gorgias_priority_set", False)),
        note_posted=bool(body.get("note_posted", False)),
        draft_text=draft_text,
    )
    return JSONResponse(content={"status": "ok"})
