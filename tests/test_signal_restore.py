"""Signal mode gives back an enclosing timer that fell due while the call overran."""

from __future__ import annotations

import contextlib
import signal
import sys
import time
from collections.abc import Iterator
from types import FrameType

import _targets
import pytest

from calltimeout import CallTimeout, run

if sys.platform == "win32":
    pytest.skip("SIGALRM is POSIX", allow_module_level=True)


@pytest.fixture
def ticks() -> Iterator[list[float]]:
    hits: list[float] = []

    def count(signum: int, frame: FrameType | None) -> None:
        hits.append(time.monotonic())

    previous = signal.signal(signal.SIGALRM, count)
    try:
        yield hits
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


def _overruns(until: float) -> str:
    # Catches the timeout, then keeps working past the enclosing timer's due time.
    with contextlib.suppress(CallTimeout):
        _targets.spin(30.0)
    _targets.spin(until - time.monotonic())
    return "late"


def test_an_enclosing_one_shot_timer_that_fell_due_still_fires(ticks: list[float]) -> None:
    signal.setitimer(signal.ITIMER_REAL, 0.15)
    with pytest.raises(CallTimeout):
        run(_overruns, 0.1, args=(time.monotonic() + 0.3,), mode="signal")
    _targets.spin(0.1)
    assert len(ticks) == 1
    assert signal.getitimer(signal.ITIMER_REAL) == (0.0, 0.0)


def test_an_enclosing_periodic_timer_that_fell_due_stays_armed(ticks: list[float]) -> None:
    signal.setitimer(signal.ITIMER_REAL, 0.15, 0.1)
    with pytest.raises(CallTimeout):
        run(_overruns, 0.1, args=(time.monotonic() + 0.3,), mode="signal")
    _targets.spin(0.25)
    assert len(ticks) >= 2, ticks
    delay, interval = signal.getitimer(signal.ITIMER_REAL)
    assert delay > 0
    assert interval == pytest.approx(0.1)
