"""Run a callable in a daemon thread and wait for it with a timeout."""

from __future__ import annotations

import contextvars
import threading
import time
from collections.abc import Callable, Mapping
from typing import TypeVar

from ._errors import Expired
from ._text import call_name
from ._validate import reject_coroutine

T = TypeVar("T")


def thread_name(fn: object) -> str:
    """Name a worker thread after its call so a lingering one is recognisable."""
    return f"calltimeout:{call_name(fn)}"


def run_in_thread(
    fn: Callable[..., T],
    timeout: float,
    args: tuple[object, ...],
    kwargs: Mapping[str, object],
) -> T:
    """Run fn in a daemon thread and return its result within the budget.

    A timed-out call is not killed: Python cannot interrupt a running thread. The
    caller stops waiting and raises, but a non-cooperative call keeps running in
    the background until it returns on its own or the process exits. A call that ends
    after the deadline also timed out, even if it ended before the caller noticed.
    """
    deadline = time.monotonic() + timeout
    result: list[T] = []
    error: list[BaseException] = []
    finished: list[float] = []
    # Same as asyncio.to_thread: the call sees the caller's context variables.
    context = contextvars.copy_context()

    def target() -> None:
        try:
            result.append(context.run(fn, *args, **kwargs))
        except BaseException as exc:
            error.append(exc)
        finally:
            finished.append(time.monotonic())

    thread = threading.Thread(target=target, name=thread_name(fn), daemon=True)
    thread.start()
    # Thread.join() always returns None: is_alive() tells whether it timed out. A call
    # holding the GIL can also end after the deadline, before this thread runs again: what
    # it returned or raised then came too late, as in process mode.
    thread.join(max(deadline - time.monotonic(), 0.0))
    if thread.is_alive() or finished[0] > deadline:
        raise Expired
    if error:
        raise error[0]
    return reject_coroutine(result[0])
