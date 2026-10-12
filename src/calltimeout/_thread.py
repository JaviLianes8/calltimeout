"""Run a callable in a daemon thread and wait for it with a timeout."""

from __future__ import annotations

import contextvars
import threading
from collections.abc import Callable, Mapping
from typing import TypeVar

from ._errors import Expired
from ._validate import reject_coroutine

T = TypeVar("T")


def thread_name(fn: object) -> str:
    """Name a worker thread after its call so a lingering one is recognisable."""
    name = getattr(fn, "__qualname__", None) or type(fn).__qualname__
    return f"calltimeout:{name}"


def run_in_thread(
    fn: Callable[..., T],
    timeout: float,
    args: tuple[object, ...],
    kwargs: Mapping[str, object],
) -> T:
    """Run fn in a daemon thread and return its result within the budget.

    A timed-out call is not killed: Python cannot interrupt a running thread. The
    caller stops waiting and raises, but a non-cooperative call keeps running in
    the background until it returns on its own or the process exits.
    """
    result: list[T] = []
    error: list[BaseException] = []
    # Same as asyncio.to_thread: the call sees the caller's context variables.
    context = contextvars.copy_context()

    def target() -> None:
        try:
            result.append(context.run(fn, *args, **kwargs))
        except BaseException as exc:
            error.append(exc)

    thread = threading.Thread(target=target, name=thread_name(fn), daemon=True)
    thread.start()
    thread.join(timeout)
    if thread.is_alive():
        raise Expired
    if error:
        raise error[0]
    return reject_coroutine(result[0])
