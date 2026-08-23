"""Small dependency facades shared by the FastAPI routers.

The application module historically exposed database and transport symbols and
the console tests patch those symbols directly. Routers use this resolver at
call time so that the public ``bb_webhook.app`` seams remain useful without
importing the composition root back into a router.
"""

from __future__ import annotations

import sys
from typing import Any, Callable

from . import database
from .config import get_settings as _config_get_settings

_MISSING = object()
_APP_MODULE_NAME = "bb_webhook.app"


def resolve(name: str, default: Any) -> Any:
    """Return a patched app-level dependency, or its router default."""
    app_module = sys.modules.get(_APP_MODULE_NAME)
    if app_module is not None:
        candidate = getattr(app_module, name, _MISSING)
        if candidate is not _MISSING:
            return candidate
    return default


def database_function(name: str) -> Callable[..., Any]:
    """Resolve a database function while preserving app-module patch seams."""
    return resolve(name, getattr(database, name))


def get_settings() -> Any:
    """Resolve settings through the app facade when tests replace it."""
    return resolve("get_settings", _config_get_settings)()


def get_db() -> Any:
    """Return the configured database path for FastAPI dependencies."""
    return get_settings().db_path_absolute
