"""Bounded synchronous child process lifecycle for the single-job processor."""
from __future__ import annotations

import os
import selectors
import signal
import subprocess
import time


class OutputLimitExceeded(RuntimeError):
    pass


def run_bounded(command, *, timeout, env, capture_output=True, text=True, cwd=None):
    """Return a CompletedProcess with bounded output and no surviving group.

    Never retain unlimited communicate() output. A fresh session isolates child
    cleanup from the processor. BaseException cleanup also covers interruption.
    This synchronous helper enforces its own deadline; it does not promise that
    asyncio cancellation can interrupt a synchronous caller.
    """
    if timeout <= 0:
        raise ValueError("process timeout must be positive")
    child = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             env=env, cwd=cwd, start_new_session=True, close_fds=True)
    selector = selectors.DefaultSelector()
    output = {"stdout": bytearray(), "stderr": bytearray()}
    limits = {"stdout": 1024 * 1024, "stderr": 128 * 1024}
    deadline = time.monotonic() + timeout
    try:
        for name in output:
            stream = getattr(child, name)
            os.set_blocking(stream.fileno(), False)
            selector.register(stream, selectors.EVENT_READ, name)
        while selector.get_map():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise subprocess.TimeoutExpired("Hermes", timeout)
            for key, _ in selector.select(min(remaining, 0.1)):
                chunk = os.read(key.fd, 65536)
                if not chunk:
                    selector.unregister(key.fileobj)
                    continue
                target = output[key.data]
                if len(target) + len(chunk) > limits[key.data]:
                    raise OutputLimitExceeded("Hermes output exceeded limit")
                target.extend(chunk)
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise subprocess.TimeoutExpired("Hermes", timeout)
        child.wait(timeout=remaining)
        return subprocess.CompletedProcess(
            command, child.returncode,
            bytes(output["stdout"]).decode("utf-8", errors="strict"),
            bytes(output["stderr"]).decode("utf-8", errors="replace"))
    finally:
        # Kill the whole group even when its leader already exited or a grandchild
        # closed inherited pipes. TERM then KILL is bounded; reap our direct child.
        try:
            os.killpg(child.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            child.wait(timeout=0.3)
        except subprocess.TimeoutExpired:
            pass
        try:
            os.killpg(child.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        child.wait()
        selector.close()
        child.stdout.close()
        child.stderr.close()
