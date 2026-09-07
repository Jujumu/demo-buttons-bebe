"""Bounded password CPU work, isolated from the webhook event loop/GIL."""
from __future__ import annotations

import asyncio
from concurrent.futures import ProcessPoolExecutor
from concurrent.futures.process import BrokenProcessPool
import multiprocessing
import threading
from .console_auth import verify_password

_CAPACITY = 2
_slots = threading.BoundedSemaphore(_CAPACITY)
_executor = None
_executor_lock = threading.Lock()


class PasswordVerifierBusy(RuntimeError):
    pass


def _pool():
    global _executor
    with _executor_lock:
        if _executor is None:
            # Spawn avoids inheriting live SQLite connections, event loops or
            # locks. Process isolation also covers crypt implementations that
            # retain the GIL, where a thread would still stall intake.
            _executor = ProcessPoolExecutor(max_workers=_CAPACITY, mp_context=multiprocessing.get_context("spawn"))
        return _executor


def _discard_broken(pool):
    global _executor
    with _executor_lock:
        if _executor is pool:
            _executor = None
            pool.shutdown(wait=False, cancel_futures=True)


async def verify_bounded(password: str, encoded: str) -> bool:
    if not _slots.acquire(blocking=False):
        raise PasswordVerifierBusy("Password verifier is at capacity")
    try:
        pool = _pool()
        future = pool.submit(verify_password, password, encoded)
    except BrokenProcessPool:
        _slots.release()
        _discard_broken(pool)
        raise
    except Exception:
        _slots.release()
        raise
    # Release when the concurrent future completes, not when an HTTP caller
    # disconnects. Cancellation must not admit unbounded still-running work.
    future.add_done_callback(lambda completed: _slots.release())
    try:
        return bool(await asyncio.wrap_future(future))
    except BrokenProcessPool:
        _discard_broken(pool)
        raise
