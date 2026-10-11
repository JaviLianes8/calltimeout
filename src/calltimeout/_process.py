"""Run a callable in a separate process that can be truly terminated."""

from __future__ import annotations

import multiprocessing
from collections.abc import Callable, Mapping
from multiprocessing.queues import Queue as MPQueue
from queue import Empty
from typing import TypeVar, cast

from ._errors import CallTimeout

T = TypeVar("T")


def _target(
    queue: MPQueue[tuple[bool, object]],
    fn: Callable[..., object],
    args: tuple[object, ...],
    kwargs: Mapping[str, object],
) -> None:
    try:
        queue.put((True, fn(*args, **kwargs)))
    except BaseException as exc:
        queue.put((False, exc))


def run_in_process(
    fn: Callable[..., T],
    timeout: float,
    args: tuple[object, ...],
    kwargs: Mapping[str, object],
) -> T:
    """Run fn in a child process, terminating it if it overruns the budget.

    Unlike thread mode this truly stops the work on timeout, but fn, its arguments
    and its result must be picklable so they can cross the process boundary.
    """
    ctx = multiprocessing.get_context()
    queue: MPQueue[tuple[bool, object]] = ctx.Queue()
    process = ctx.Process(target=_target, args=(queue, fn, args, dict(kwargs)))
    process.start()
    try:
        ok, payload = queue.get(timeout=timeout)
    except Empty:
        process.terminate()
        process.join()
        raise CallTimeout(timeout) from None
    finally:
        queue.close()
    process.join()
    if ok:
        return cast(T, payload)
    assert isinstance(payload, BaseException)
    raise payload
