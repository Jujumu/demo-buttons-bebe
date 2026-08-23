"""Cookie-backed authentication for the human support console."""

from __future__ import annotations

import hmac

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, RedirectResponse, Response

from .. import deps
from ..console_auth import (
    build_session_token,
    safe_next_path,
    verify_password,
    verify_session_token,
)

router = APIRouter()

_COOKIE_NAME = "bb_console_session"
_LOGIN_MAX_REQUESTS_PER_MINUTE = 12
_LOGIN_COOKIE_TTL_SECONDS = 12 * 60 * 60


def _client_ip(request: Request) -> str:
    """Use the proxy-provided client address, with a safe local fallback."""
    forwarded = request.headers.get("x-forwarded-for", "").split(",", 1)[0].strip()
    if forwarded and len(forwarded) <= 128:
        return forwarded
    return request.client.host if request.client else "unknown"


def _login_allowed(request: Request) -> bool:
    # Importing the existing limiter keeps login attempts bounded by the same
    # process-wide, deterministic mechanism used by the webhook receiver.
    from ..middleware.rate_limit import _check_rate_limit

    return _check_rate_limit(_client_ip(request), _LOGIN_MAX_REQUESTS_PER_MINUTE)


def _session_username(request: Request) -> str | None:
    settings = deps.get_settings()
    if not settings.console_session_secret:
        return None
    return verify_session_token(
        request.cookies.get(_COOKIE_NAME, ""), settings.console_session_secret
    )


def _auth_unconfigured() -> JSONResponse:
    return JSONResponse(status_code=503, content={"error": "console_auth_unconfigured"})


@router.post("/auth/login")
async def auth_login(request: Request) -> JSONResponse:
    """Validate the form credentials and issue an HttpOnly session cookie."""
    if not _login_allowed(request):
        return JSONResponse(status_code=429, content={"error": "too_many_attempts"})
    settings = deps.get_settings()
    if not settings.console_password_hash or not settings.console_session_secret:
        return _auth_unconfigured()
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"error": "invalid_json"})
    if not isinstance(body, dict):
        return JSONResponse(status_code=400, content={"error": "invalid_json_object"})

    username = body.get("username", "")
    password = body.get("password", "")
    if not isinstance(username, str) or not isinstance(password, str):
        return JSONResponse(status_code=400, content={"error": "invalid_credentials"})
    if not hmac.compare_digest(username.strip(), settings.console_username):
        return JSONResponse(status_code=401, content={"error": "invalid_credentials"})
    if not verify_password(password, settings.console_password_hash):
        return JSONResponse(status_code=401, content={"error": "invalid_credentials"})

    redirect = safe_next_path(body.get("next"))
    token = build_session_token(username.strip(), settings.console_session_secret)
    response = JSONResponse(content={"ok": True, "redirect": redirect})
    response.set_cookie(
        _COOKIE_NAME,
        token,
        max_age=_LOGIN_COOKIE_TTL_SECONDS,
        httponly=True,
        secure=not settings.demo_mode,
        samesite="strict",
        path="/",
    )
    return response


@router.get("/auth/session")
async def auth_session(request: Request) -> JSONResponse:
    username = _session_username(request)
    if username is None:
        return JSONResponse(status_code=401, content={"error": "not_authenticated"})
    return JSONResponse(content={"authenticated": True, "username": username})


@router.get("/auth/check")
async def auth_check(request: Request) -> Response:
    """Small forward-auth target used by Caddy for API and admin routes."""
    if _session_username(request) is None:
        return JSONResponse(status_code=401, content={"error": "not_authenticated"})
    return Response(status_code=204)


@router.get("/auth/page-check")
async def auth_page_check(request: Request) -> Response:
    """Redirect unauthenticated browser navigation to the standalone login."""
    if _session_username(request) is None:
        return RedirectResponse(url="/console/login", status_code=302)
    return Response(status_code=204)


@router.post("/auth/logout")
async def auth_logout() -> Response:
    response = JSONResponse(content={"ok": True})
    response.delete_cookie(_COOKIE_NAME, path="/")
    return response
