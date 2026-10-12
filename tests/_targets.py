"""Call targets at module level, so the spawn and forkserver start methods can pickle them."""

from __future__ import annotations

import os
import signal
import threading
import time

from calltimeout import run, with_timeout

gate = threading.Event()


def echo(value: object) -> object:
    return value


def pid() -> int:
    return os.getpid()


def slow(seconds: float) -> str:
    time.sleep(seconds)
    return "done"


def spin(seconds: float) -> int:
    # Pure Python work with no system call, to show where each mode can interrupt.
    end = time.monotonic() + seconds
    count = 0
    while time.monotonic() < end:
        count += 1
    return count


def blocks_until_gate() -> str:
    gate.wait()
    return "released"


def boom() -> None:
    raise ValueError("boom")


def hard_exit(code: int) -> None:
    os._exit(code)


def unpicklable_result() -> object:
    return threading.Lock()


class LocalOnlyError(Exception):
    def __init__(self, first: str, second: str) -> None:
        # Pickles, but cannot be rebuilt from args: unpickling calls it with one argument.
        super().__init__(f"{first}-{second}")


def raises_unrebuildable() -> None:
    raise LocalOnlyError("a", "b")


def raises_unpicklable() -> None:
    error = ValueError("carries a lock")
    error.lock = threading.Lock()  # type: ignore[attr-defined]
    raise error


def ignores_sigterm(seconds: float) -> str:
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    time.sleep(seconds)
    return "survived"


def nested_timeout() -> str:
    # The inner call overruns; the outer call must not mistake it for its own timeout.
    return run(slow, 0.05, args=(5.0,), mode="process")


def swallows_timeout(seconds: float) -> str:
    try:
        time.sleep(seconds)
    except Exception:
        return "caught it"
    return "carried on"


@with_timeout(10.0, mode="process")
def decorated_pid(offset: int) -> int:
    return os.getpid() + offset


@with_timeout(0.2, mode="process", default="stopped")
def decorated_slow(seconds: float) -> str:
    time.sleep(seconds)
    return "done"
