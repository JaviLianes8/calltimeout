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
from ._timers import give_back, kept, next_tick, read, settle
from ._validate import reject_coroutine

T = TypeVar("T")

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
    """Give a tick that is not this call's to the handler that was there before."""
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
    a handler that raises stops the retry). Code running in C that does not check for
    signals itself is only interrupted once it returns to the interpreter. A timer that
    was already armed keeps its schedule, over any number of calls, and its handler gets
    every tick that is not this call's: when due, up to 1 ms late.
    """
    check_signal_mode()
    if sys.platform == "win32":  # repeated so type checkers on Windows skip the rest
        raise NotImplementedError(_NO_SIGALRM)
    if timeout < _FLOOR:
        raise Expired  # already within the last millisecond: a tick that soon can be lost
    previous = signal.getsignal(signal.SIGALRM)
    if previous is None:
        raise RuntimeError("SIGALRM has a handler set outside Python that could not be restored")
    deadline = time.monotonic() + timeout
    settle()
    outer_due: float | None = None
    outer_interval = 0.0
    ready = taken = fired = False
    active = True
    early: list[FrameType | None] = []
    raised = CallTimeout(timeout)

    def arm(now: float) -> None:
        # Never sooner than the floor, also toward an enclosing timer that is due sooner.
        due = deadline if outer_due is None else min(deadline, outer_due)
        signal.setitimer(signal.ITIMER_REAL, max(due - now, _FLOOR))

    def pass_on(signum: int, frame: FrameType | None, due: bool) -> None:
        nonlocal outer_due, outer_interval
        signal.setitimer(signal.ITIMER_REAL, 0)
        if due and outer_due is not None:
            # This tick is consumed even if the handler raises: never deliver it twice.
            outer_due = next_tick(outer_due, outer_interval, time.monotonic())
        try:
            _pass_on(previous, signum, frame)
        finally:
            # The enclosing handler may have re-armed the timer: its new schedule.
            now = time.monotonic()
            again, interval = read(*signal.getitimer(signal.ITIMER_REAL), now)
            if again is not None:
                outer_due, outer_interval = again, interval
            arm(now)

    def expire(signum: int, frame: FrameType | None) -> None:
        nonlocal fired
        if not active:
            return  # the call is over; the outer timer is restored below
        if not ready:
            early.append(frame)  # taken before the timer was this call's: handled then
            return
        now = time.monotonic()
        if now < deadline - _FLOOR:
            due = outer_due is not None and now >= outer_due
            # Not due by the clock, and this call's timer is still running: the tick was
            # on its way before the call started, or sent by someone else.
            if due or signal.getitimer(signal.ITIMER_REAL)[0] > 0:
                pass_on(signum, frame, due)
                now = time.monotonic()
        if now >= deadline - _FLOOR:
            fired = True
            raise raised
        arm(now)  # woke early: wait for whichever is due next

    signal.signal(signal.SIGALRM, expire)
    try:
        try:
            # Read and replaced at once, so no tick of the enclosing timer falls in between.
            delay, interval = signal.setitimer(signal.ITIMER_REAL, timeout)
            taken = True
            now = time.monotonic()
            outer_due, outer_interval = kept(*read(delay, interval, now))
            ready = True
            if outer_due is not None and outer_due < deadline:
                arm(now)
            while early:
                expire(signal.SIGALRM, early.pop(0))
            value = fn(*args, **kwargs)
        finally:
            # Inert first, then disarmed: a late tick can no longer re-arm the timer.
            active = False
            if taken:
                signal.setitimer(signal.ITIMER_REAL, 0)
    except BaseException as exc:
        # Also covers the alarm landing after fn returned but before the disarm.
        if fired and _caused_by(exc, raised):
            raise Expired from exc
        raise
    finally:
        signal.signal(signal.SIGALRM, previous)
        if taken:
            give_back(outer_due, outer_interval, time.monotonic())
    if fired:
        # The call caught the timeout and returned later; the budget was still exceeded.
        raise Expired
    return reject_coroutine(value)
