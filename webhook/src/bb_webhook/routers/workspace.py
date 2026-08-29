"""HTTP facade for the Team Support Workspace organ."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, JSONResponse

from ..tissues import drafts as draft_tissue
from ..tissues import shopify_context, tickets
from ..tissues import workspace as workspace_organ

router = APIRouter(prefix="/dashboard/api")

_INBOX_HTML = Path(__file__).resolve().parents[4] / "console-src" / "inbox.html"


def _json_body(body: object) -> dict:
    return body if isinstance(body, dict) else {}


@router.get("/workspace/ui", response_model=None)
async def workspace_ui() -> FileResponse | JSONResponse:
    if not _INBOX_HTML.is_file():
        return JSONResponse(status_code=404, content={"error": "inbox_missing"})
    return FileResponse(_INBOX_HTML, media_type="text/html")


@router.get("/workspace/inbox")
async def workspace_inbox(view: str = "open") -> JSONResponse:
    snapshot = workspace_organ.inbox(view)
    return JSONResponse(content=snapshot.as_dict())


@router.get("/workspace/tickets/{ticket_id}")
async def workspace_ticket(ticket_id: str, retry_shopify: bool = False) -> JSONResponse:
    result = workspace_organ.open_ticket(ticket_id, retry_shopify=retry_shopify)
    if result.status != "ok":
        return JSONResponse(status_code=404, content=result.as_dict())
    return JSONResponse(content=result.data.as_dict())


@router.post("/workspace/tickets/{ticket_id}/draft/insert")
async def workspace_draft_insert(ticket_id: str) -> JSONResponse:
    payload = workspace_organ.insert_draft(ticket_id)
    if payload["draft"]["status"] != "ok":
        return JSONResponse(status_code=404, content=payload)
    return JSONResponse(content=payload)


@router.post("/workspace/tickets/{ticket_id}/draft/discard")
async def workspace_draft_discard(ticket_id: str) -> JSONResponse:
    return JSONResponse(content=workspace_organ.discard_draft(ticket_id))


@router.post("/workspace/tickets/{ticket_id}/send")
async def workspace_send(ticket_id: str, request: Request) -> JSONResponse:
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"error": "invalid_json"})
    payload = _json_body(body)
    text = payload.get("body", "")
    close = bool(payload.get("close"))
    if not isinstance(text, str):
        return JSONResponse(status_code=400, content={"error": "invalid_body"})
    result = workspace_organ.send_reply(ticket_id, text, close=close)
    if result.status == "error":
        return JSONResponse(status_code=400, content=result.as_dict())
    if result.status == "empty":
        return JSONResponse(status_code=404, content=result.as_dict())
    return JSONResponse(content={"sent": True, "auto_sent": False, "thread": result.as_dict()})


def reset_workspace_fixtures() -> None:
    """Test helper so API tests start from the same fixture set."""
    tickets.reset_fixtures()
    shopify_context.reset_fixtures()
    draft_tissue.reset_fixtures()
