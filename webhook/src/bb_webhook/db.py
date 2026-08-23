"""Small retrying SQLite access wrapper used by the webhook database layer."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import aiosqlite

from .config import get_settings
from .logging_utils import get_logger

logger = get_logger(__name__)

_LOCK_RETRY_ATTEMPTS = 5
_LOCK_RETRY_DELAY = 0.15  # seconds


class Database:
    """Execute one SQLite statement per short-lived, retried connection."""

    def __init__(self, path: Path | str | None = None) -> None:
        self.path = Path(path) if path is not None else get_settings().db_path_absolute

    async def execute(
        self,
        sql: str,
        params: tuple = (),
        *,
        operation: str = "database",
        fetch: bool = False,
        return_rowcount: bool = False,
    ) -> Any | None:
        """Execute *sql*, retrying transient SQLite lock errors.

        Reads return ``list[aiosqlite.Row]``. Writes return ``lastrowid`` by
        default, or ``cursor.rowcount`` when ``return_rowcount`` is requested.
        The latter is required for idempotency and atomic queue claims.
        """

        for attempt in range(_LOCK_RETRY_ATTEMPTS):
            try:
                async with aiosqlite.connect(str(self.path)) as conn:
                    await conn.execute("PRAGMA busy_timeout=3000")
                    if fetch:
                        conn.row_factory = aiosqlite.Row
                        cursor = await conn.execute(sql, params)
                        result = await cursor.fetchall()
                        await cursor.close()
                        return result

                    cursor = await conn.execute(sql, params)
                    affected = cursor.rowcount
                    row = cursor.lastrowid
                    await conn.commit()
                    await cursor.close()
                    return affected if return_rowcount else row
            except aiosqlite.OperationalError as exc:
                if "locked" in str(exc).lower() and attempt < _LOCK_RETRY_ATTEMPTS - 1:
                    logger.warning(
                        "DB locked on %s — retry %d/%d",
                        operation,
                        attempt + 1,
                        _LOCK_RETRY_ATTEMPTS,
                    )
                    await asyncio.sleep(_LOCK_RETRY_DELAY)
                    continue
                raise
        return None

    async def fetch(self, sql: str, params: tuple = (), *, operation: str = "database") -> list[Any]:
        """Fetch all rows for a SELECT statement."""

        return await self.execute(sql, params, operation=operation, fetch=True) or []
