"""Liveness and readiness probes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from .. import deps

router = APIRouter()


@router.get("/health")
async def health() -> dict[str, str]:
    """Liveness probe — always returns 200 if the process is alive."""
    return {"status": "ok"}


@router.get("/ready")
async def ready() -> JSONResponse:
    """Readiness probe — checks the database path and Gorgias credentials."""
    settings = deps.get_settings()
    checks: dict[str, Any] = {}
    try:
        db_path = settings.db_path_absolute
        checks["db"] = "ok" if db_path.parent.exists() else "missing"
    except Exception as exc:
        checks["db"] = f"error: {exc}"
    checks["gorgias_configured"] = bool(settings.gorgias_auth)
    all_ok = all(value == "ok" or value is True for value in checks.values())
    return JSONResponse(
        status_code=200 if all_ok else 503,
        content={"status": "ready" if all_ok else "not_ready", "checks": checks},
    )
