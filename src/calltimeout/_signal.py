"""Interrupt a call in place with SIGALRM (POSIX, main thread only)."""

from __future__ import annotations

import signal
import sys
import threading
import time
from collections.abc import Callable, Mapping
from types import FrameType
from typing import Any, TypeVar

from ._errors import CallTimeout, Expired
from ._validate import reject_coroutine

T = TypeVar("T")

# Smallest delay used to re-arm a timer that is already due: zero would disarm it.
_SOON = 1e-6

_NO_SIGALRM = "mode 'signal' needs SIGALRM, which Windows lacks; use 'thread' or 'process'"


def check_signal_mode() -> None:
    """Raise if this platform or thread cannot use SIGALRM."""
    if sys.platform == "win32":
        raise NotImplementedError(_NO_SIGALRM)
    if threading.current_thread() is not threading.main_thread():
        raise RuntimeError("mode 'signal' only works in the main thread")


def _pass_on(previous: Any, signum: int, frame: FrameType | None) -> None:
    """Give an enclosing timer's tick to the handler that was there before."""
    if callable(previous):
        previous(signum, frame)
    elif previous == signal.SIG_DFL:
        # The default action ends the process, which is what that timer was set up for.
        signal.signal(signum, signal.SIG_DFL)
        signal.raise_signal(signum)


def run_with_signal(
    fn: Callable[..., T],
    timeout: float,
    args: tuple[object, ...],
    kwargs: Mapping[str, object],
) -> T:
    """Run fn in this thread and raise CallTimeout inside it when the budget runs out.

    Pure Python code and blocking system calls are interrupted where they are (PEP 475:
    a handler that raises stops the retry). Code running in C without returning to the
    interpreter is only interrupted once it does. A timer that was already armed keeps
    its schedule and its handler still runs when it is due.
    """
    check_signal_mode()
    if sys.platform == "win32":  # repeated so type checkers on Windows skip the rest
        raise NotImplementedError(_NO_SIGALRM)
    start = time.monotonic()
    deadline = start + timeout
    outer_delay, outer_interval = signal.getitimer(signal.ITIMER_REAL)
    outer_due = start + outer_delay if outer_delay > 0 else None
    fired = False

    def arm(now: float) -> None:
        due = deadline if outer_due is None else min(deadline, outer_due)
        signal.setitimer(signal.ITIMER_REAL, max(due - now, _SOON))

    def expire(signum: int, frame: FrameType | None) -> None:
        nonlocal fired, outer_due, outer_interval
        now = time.monotonic()
        if now >= deadline:
            fired = True
            raise CallTimeout(timeout)
        if outer_due is not None and now >= outer_due:
            signal.setitimer(signal.ITIMER_REAL, 0)
            _pass_on(previous, signum, frame)
            # The enclosing handler may have re-armed the timer: that is its new schedule.
            delay, interval = signal.getitimer(signal.ITIMER_REAL)
            now = time.monotonic()
            if delay > 0:
                outer_due, outer_interval = now + delay, interval
            else:
                outer_due = now + outer_interval if outer_interval > 0 else None
        arm(now)  # also covers waking a little early: wait for whichever is due next

    previous = signal.signal(signal.SIGALRM, expire)
    try:
        arm(start)
        try:
            value = fn(*args, **kwargs)
        except BaseException as exc:
            if fired:
                raise Expired from exc
            raise
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
    except CallTimeout as exc:
        # The alarm can land after the call returned but before the timer was disarmed.
        if fired:
            raise Expired from exc
        raise
    finally:
        signal.signal(signal.SIGALRM, signal.SIG_DFL if previous is None else previous)
        if outer_due is not None:
            left = outer_due - time.monotonic()
            signal.setitimer(signal.ITIMER_REAL, max(left, _SOON), outer_interval)
    if fired:
        # The call caught the timeout and carried on; the budget was still exceeded.
        raise Expired
    return reject_coroutine(value)
