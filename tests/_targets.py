"""Call targets at module level, so the spawn and forkserver start methods can pickle them."""

from __future__ import annotations

import os
import signal
import sys
import threading
import time
import types
from typing import Any

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


def crash_leaving_grandchild(seconds: float) -> None:
    # The forked grandchild inherits the result pipe and keeps it open after we die.
    if sys.platform != "win32" and os.fork() == 0:
        time.sleep(seconds)
        os._exit(0)
    os._exit(5)


def cleans_up_on_sigterm(marker: str, seconds: float) -> None:
    # SIGTERM becomes SystemExit, so the finally clause gets its grace period to run.
    signal.signal(signal.SIGTERM, lambda signum, frame: sys.exit(0))
    try:
        time.sleep(seconds)
    finally:
        with open(marker, "w", encoding="utf-8") as handle:
            handle.write("cleaned up")


def put_in_queue(queue: Any, lock: Any) -> str:
    with lock:
        queue.put("sent")
    return "put"


def write_later(marker: str) -> str:
    # A non-daemon thread the child's normal shutdown waits for.
    def write() -> None:
        time.sleep(0.2)
        with open(marker, "w", encoding="utf-8") as handle:
            handle.write("flushed")

    threading.Thread(target=write).start()
    return "returned"


def touch(marker: str) -> None:
    with open(marker, "w", encoding="utf-8") as handle:
        handle.write("ran")


def child_only_result() -> object:
    # Pickles in the child, but its module does not exist in the parent.
    module = types.ModuleType("ghost_module")
    exec("class Ghost:\n    pass\n", module.__dict__)
    sys.modules["ghost_module"] = module
    return module.Ghost()


assigned_pid = with_timeout(30.0, mode="process")(pid)


class SlowToPickle:
    """An argument whose pickling takes a while, to spend the budget before the start."""

    def __reduce__(self) -> tuple[object, tuple[str]]:
        time.sleep(0.6)
        return (str, ("pickled",))


def touch_with(marker: str, extra: object) -> object:
    touch(marker)
    return extra


def kill_self(signum: int) -> None:
    os.kill(os.getpid(), signum)
