"""The enclosing ITIMER_REAL timer a signal-mode call borrows, and its schedule."""

from __future__ import annotations

import math
import signal
import sys
import time

# Smallest delay used to give back an enclosing timer that is already due: zero would
# disarm it.
_SOON = 1e-6

# How close an enclosing timer read as a call starts must be to the schedule the previous
# call gave back for that schedule to be kept. Read anew, it would gain the microseconds
# spent reading and setting it at every call, and over many calls those add up.
_SAME = 5e-4

# How long before its expiry the enclosing timer is left alone. Replaced in the instant it
# expires (it reads no time left, its signal not yet sent), its tick can be lost: Linux 6.6
# sent it within 0.07 ms when left alone, and dropped about half of them when replaced.
_GUARD = 2e-4

# The enclosing timer's schedule (when due, interval) as the last call gave it back.
_given_back: list[tuple[float, float]] = []


def next_tick(due: float, interval: float, now: float) -> float | None:
    """When a periodic timer's next tick is due, on its own schedule; None if one-shot.

    Counted from when this tick was due, not from when it ran, so lateness does not add
    up; ticks already missed are skipped, as Linux does when it re-arms the timer.
    """
    if interval <= 0:
        return None
    return due + (math.floor((now - due) / interval) + 1) * interval


def read(delay: float, interval: float, now: float) -> tuple[float | None, float]:
    """When a timer read at now as (delay, interval) is next due (None if disarmed).

    Linux re-arms an interval timer only once its signal is taken, so read in between it
    shows no delay left: that tick is on its way, and the next one is an interval away.
    """
    if delay > 0:
        return now + delay, interval
    return (now + interval if interval > 0 else None), interval


def kept(due: float | None, interval: float) -> tuple[float | None, float]:
    """The schedule last given back, if the timer read is still that one; else the read."""
    if due is None or not _given_back:
        return due, interval
    known, every = _given_back[0]
    if abs(every - interval) > _SOON:
        return due, interval
    if every > 0:
        known += round((due - known) / every) * every
    return (known if abs(known - due) < _SAME else due), interval


def give_back(due: float | None, interval: float, now: float) -> None:
    """Re-arm the enclosing timer at now on its schedule, and remember that schedule."""
    if sys.platform == "win32":  # only reached through run_with_signal; for type checkers
        raise NotImplementedError("SIGALRM is POSIX")
    _given_back.clear()
    if due is not None:
        _given_back.append((due, interval))
        signal.setitimer(signal.ITIMER_REAL, max(due - now, _SOON), interval)


def settle() -> None:
    """Return once the enclosing timer is not about to fire, letting a tick due now through.

    Bounded: a timer that keeps re-arming itself sooner than the guard is taken anyway.
    """
    if sys.platform == "win32":  # only reached through run_with_signal; for type checkers
        raise NotImplementedError("SIGALRM is POSIX")
    for _ in range(3):
        delay, interval = signal.getitimer(signal.ITIMER_REAL)
        if delay > _GUARD:
            return
        if delay == 0 and interval == 0:
            # Disarmed, or a one-shot timer that just expired: only the schedule the last
            # call gave back tells them apart.
            if not _given_back or _given_back[0][1] > 0:
                return
            delay = _given_back[0][0] - time.monotonic()
            if abs(delay) > _GUARD:
                return  # long fired, or cancelled before it was due
        time.sleep(max(delay, 0.0) + _GUARD)
