"""Console HTTP door onto the helpdesk organ. Same invoke() as MCP/CLI."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from ..helpdesk_door import handle_tool

router = APIRouter(prefix="/dashboard/api")


@router.post("/helpdesk")
async def helpdesk_invoke(request: Request) -> JSONResponse:
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"ok": False, "error": "bad_request", "message": "invalid_json"})
    if not isinstance(body, dict):
        return JSONResponse(status_code=400, content={"ok": False, "error": "bad_request", "message": "invalid_json_object"})
    tool = body.get("tool")
    arguments = body.get("arguments") or {}
    if not isinstance(tool, str) or not tool.startswith("helpdesk."):
        return JSONResponse(status_code=400, content={"ok": False, "error": "bad_request", "message": "tool is required"})
    if not isinstance(arguments, dict):
        return JSONResponse(status_code=400, content={"ok": False, "error": "bad_request", "message": "arguments must be an object"})
    payload = handle_tool(tool, arguments)
    return JSONResponse(content=payload, status_code=200 if payload.get("ok") else 400)
