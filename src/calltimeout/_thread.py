"""Run a callable in a daemon thread and wait for it with a timeout."""

from __future__ import annotations

import threading
from collections.abc import Callable, Mapping
from typing import TypeVar

from ._errors import CallTimeout

T = TypeVar("T")


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

    def target() -> None:
        try:
            result.append(fn(*args, **kwargs))
        except BaseException as exc:
            error.append(exc)

    thread = threading.Thread(target=target, daemon=True)
    thread.start()
    thread.join(timeout)
    if thread.is_alive():
        raise CallTimeout(timeout)
    if error:
        raise error[0]
    return result[0]
