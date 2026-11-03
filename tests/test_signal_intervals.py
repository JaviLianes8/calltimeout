"""Signal mode: an interval timer running around the calls keeps its own schedule."""

from __future__ import annotations

import signal
import sys
import time
from collections.abc import Callable
from types import FrameType

import pytest

from calltimeout import run

if sys.platform == "win32":
    pytest.skip("SIGALRM is POSIX", allow_module_level=True)

INTERVAL = 0.01

# How far behind its schedule the last tick may be: a tick due during a call runs up to
# 1 ms late (no timer is armed for less), and that lateness must not add up.
SLACK = 0.004


def _under_interval_timer(work: Callable[[], None]) -> tuple[int, int, float]:
    """Run work under a 10 ms interval timer: ticks seen, ticks due, last tick's lateness."""
    ticks: list[float] = []

    def tick(signum: int, frame: FrameType | None) -> None:
        ticks.append(time.monotonic())

    previous = signal.signal(signal.SIGALRM, tick)
    try:
        start = time.monotonic()
        signal.setitimer(signal.ITIMER_REAL, INTERVAL, INTERVAL)
        work()
        stop = time.monotonic()
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)
    due = int((stop - start) / INTERVAL)
    behind = (ticks[-1] - start) - INTERVAL * len(ticks)
    return len(ticks), due, behind


def _one_long_call() -> None:
    run(time.sleep, 10.0, args=(1.5,), mode="signal")


def _many_short_calls() -> None:
    for _ in range(200):
        run(time.sleep, 10.0, args=(0.005,), mode="signal")


@pytest.mark.parametrize("work", [_one_long_call, _many_short_calls], ids=["long", "short"])
def test_an_interval_timer_keeps_its_schedule_across_calls(work: Callable[[], None]) -> None:
    seen, due, behind = _under_interval_timer(work)
    assert seen >= due - 1  # none lost (the last may be just about due)
    assert behind < SLACK


def test_the_same_timer_without_calls_is_on_schedule() -> None:
    # The yardstick: the same measurement around plain sleeps.
    seen, due, behind = _under_interval_timer(lambda: time.sleep(1.5))
    assert seen >= due - 1
    assert behind < SLACK


def test_an_interval_timer_read_as_it_fires_is_kept(monkeypatch: pytest.MonkeyPatch) -> None:
    # Linux re-arms an interval timer only once its signal is taken: a read in between
    # shows no delay left but the interval, and the timer is still running. The call reads
    # it as it replaces it with its own.
    real = signal.setitimer
    reads: list[int] = []

    def as_it_fires(which: int, seconds: float, interval: float = 0.0) -> tuple[float, float]:
        reads.append(which)
        old = real(which, seconds, interval)
        return (0.0, INTERVAL) if len(reads) == 1 else old

    previous = signal.signal(signal.SIGALRM, lambda signum, frame: None)
    try:
        signal.setitimer(signal.ITIMER_REAL, INTERVAL, INTERVAL)
        monkeypatch.setattr(signal, "setitimer", as_it_fires)
        run(time.sleep, 10.0, args=(0.03,), mode="signal")
        monkeypatch.undo()
        delay, interval = signal.getitimer(signal.ITIMER_REAL)
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)
    assert reads
    assert interval == pytest.approx(INTERVAL)
    assert 0 < delay <= INTERVAL + 0.001
