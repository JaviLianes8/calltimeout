"""Interrupt a call in place with SIGALRM (POSIX, main thread only)."""

from __future__ import annotations

import math
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

# Smallest delay used to give back an enclosing timer that is already due: zero would
# disarm it.
_SOON = 1e-6

# Shortest delay the timer is armed for. A tick due sooner can land after the handler
# returns (or before fn starts) but before the interrupted system call blocks again: it is
# then lost until the call ends on its own. So a deadline closer than this counts as reached.
_FLOOR = 1e-3

_NO_SIGALRM = "mode 'signal' needs SIGALRM, which Windows lacks; use 'thread' or 'process'"


def check_signal_mode() -> None:
    """Raise if this platform or thread cannot use SIGALRM."""
    if sys.platform == "win32":
        raise NotImplementedError(_NO_SIGALRM)
    if threading.current_thread() is not threading.main_thread():
        raise RuntimeError("mode 'signal' only works in the main thread")


def _caused_by(exc: BaseException, raised: CallTimeout) -> bool:
    """True if exc is our timeout or an Exception raised while handling it."""
    seen: set[int] = set()
    pending: list[BaseException] = [exc]
    while pending:
        current = pending.pop()
        if current is raised:
            return True
        if id(current) in seen or not isinstance(current, Exception):
            continue  # KeyboardInterrupt, SystemExit and friends always propagate
        seen.add(id(current))
        # Both links: "raise E from other" inside the handler still has the timeout as
        # its context.
        pending.extend(e for e in (current.__cause__, current.__context__) if e is not None)
    return False


def _pass_on(previous: Any, signum: int, frame: FrameType | None) -> None:
    """Give an enclosing timer's tick to the handler that was there before."""
    if callable(previous):
        previous(signum, frame)
    elif previous == signal.SIG_DFL:
        # The default action ends the process, which is what that timer was set up for.
        signal.signal(signum, signal.SIG_DFL)
        signal.raise_signal(signum)


def _next_tick(due: float, interval: float, now: float) -> float | None:
    """When a periodic timer's next tick is due, on its own schedule; None if one-shot.

    Counted from when this tick was due, not from when it ran, so lateness does not add
    up; ticks already missed are skipped, as Linux does when it re-arms the timer.
    """
    if interval <= 0:
        return None
    return due + (math.floor((now - due) / interval) + 1) * interval


def _outer_timer(now: float) -> tuple[float | None, float]:
    """When the armed ITIMER_REAL is next due (None if disarmed), and its interval.

    Linux re-arms an interval timer only once its signal is taken, so read in between it
    shows no delay left. That tick is taken on the way back from this very call, and
    reaches the handler in place: the next one is an interval away.
    """
    if sys.platform == "win32":  # only reached through run_with_signal; for type checkers
        raise NotImplementedError(_NO_SIGALRM)
    delay, interval = signal.getitimer(signal.ITIMER_REAL)
    if delay > 0:
        return now + delay, interval
    return (now + interval if interval > 0 else None), interval


def run_with_signal(
    fn: Callable[..., T],
    timeout: float,
    args: tuple[object, ...],
    kwargs: Mapping[str, object],
) -> T:
    """Run fn in this thread and raise CallTimeout inside it when the budget runs out.

    Pure Python code and blocking system calls are interrupted where they are (PEP 475:
    a handler that raises stops the retry). Code running in C that does not check for
    signals itself is only interrupted once it returns to the interpreter. A timer that
    was already armed keeps its schedule and its handler still runs when it is due, up to
    1 ms late, without that lateness adding up for an interval timer.
    """
    check_signal_mode()
    if sys.platform == "win32":  # repeated so type checkers on Windows skip the rest
        raise NotImplementedError(_NO_SIGALRM)
    if timeout < _FLOOR:
        raise Expired  # already within the last millisecond: a tick that soon can be lost
    start = time.monotonic()
    deadline = start + timeout
    outer_due, outer_interval = _outer_timer(start)
    fired = False
    active = True
    raised = CallTimeout(timeout)

    def arm(now: float) -> None:
        # Never sooner than the floor, also toward an enclosing timer that is due sooner.
        due = deadline if outer_due is None else min(deadline, outer_due)
        signal.setitimer(signal.ITIMER_REAL, max(due - now, _FLOOR))

    def expire(signum: int, frame: FrameType | None) -> None:
        nonlocal fired, outer_due, outer_interval
        if not active:
            return  # the call is over; the outer timer is restored below
        now = time.monotonic()
        if now < deadline - _FLOOR and outer_due is not None and now >= outer_due:
            signal.setitimer(signal.ITIMER_REAL, 0)
            # This tick is consumed even if the handler raises: never deliver it twice.
            outer_due = _next_tick(outer_due, outer_interval, now)
            try:
                _pass_on(previous, signum, frame)
            finally:
                # The enclosing handler may have re-armed the timer: its new schedule.
                now = time.monotonic()
                due, interval = _outer_timer(now)
                if due is not None:
                    outer_due, outer_interval = due, interval
                arm(now)
        if now >= deadline - _FLOOR:
            fired = True
            raise raised
        arm(now)  # woke early: wait for whichever is due next

    if signal.getsignal(signal.SIGALRM) is None:
        raise RuntimeError("SIGALRM has a handler set outside Python that could not be restored")
    previous = signal.signal(signal.SIGALRM, expire)
    try:
        try:
            arm(start)
            value = fn(*args, **kwargs)
        finally:
            # Inert first, then disarmed: a late tick can no longer re-arm the timer.
            active = False
            signal.setitimer(signal.ITIMER_REAL, 0)
    except BaseException as exc:
        # Also covers the alarm landing after fn returned but before the disarm.
        if fired and _caused_by(exc, raised):
            raise Expired from exc
        raise
    finally:
        signal.signal(signal.SIGALRM, signal.SIG_DFL if previous is None else previous)
        if outer_due is not None:
            left = outer_due - time.monotonic()
            signal.setitimer(signal.ITIMER_REAL, max(left, _SOON), outer_interval)
    if fired:
        # The call caught the timeout and returned later; the budget was still exceeded.
        raise Expired
    return reject_coroutine(value)
