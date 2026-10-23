"""Signal mode: no timer is ever armed for less than 1 ms, and that last millisecond counts.

A tick due sooner can land before the interrupted system call blocks again and be lost,
so the call would overrun by its whole length. Some tests drive the module's clock
(``_signal.time``) to put a tick at an exact point; the timers and handlers are real.
"""

from __future__ import annotations

import contextlib
import signal
import sys
import time
from types import FrameType
from typing import Any

import _targets
import pytest

from calltimeout import CallTimeout, _signal, run

if sys.platform == "win32":
    pytest.skip("SIGALRM is POSIX", allow_module_level=True)

FLOOR = 1e-3


@pytest.fixture(autouse=True)
def _clean_timer() -> Any:
    yield
    signal.setitimer(signal.ITIMER_REAL, 0)
    signal.signal(signal.SIGALRM, signal.SIG_DFL)


class _Clock:
    """The real monotonic clock plus a settable jump, keeping every reading."""

    def __init__(self) -> None:
        self.jump = 0.0
        self.readings: list[float] = []

    def monotonic(self) -> float:
        value = time.monotonic() + self.jump
        self.readings.append(value)
        return value

    def move_to(self, when: float) -> None:
        self.jump = when - time.monotonic()


def _record_setitimer(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    """Record the library's setitimer delays; tests arm their own timers with the real one."""
    real = signal.setitimer
    delays: list[float] = []

    def setitimer(which: int, seconds: float, interval: float = 0.0) -> tuple[float, float]:
        delays.append(seconds)
        return real(which, seconds, interval)

    monkeypatch.setattr(signal, "setitimer", setitimer)
    return delays


def test_a_budget_under_a_millisecond_counts_as_used_up_and_never_starts_the_call() -> None:
    called: list[float] = []

    def wait(seconds: float) -> None:
        called.append(seconds)
        time.sleep(seconds)

    for budget in (1e-6, 5e-4, 999e-6):
        started = time.monotonic()
        with pytest.raises(CallTimeout):
            run(wait, budget, args=(1.0,), mode="signal")
        assert time.monotonic() - started < 0.5
    assert run(wait, 1e-6, args=(1.0,), mode="signal", default="late") == "late"
    assert called == []


def _raises_a_cause_cycle_after_the_timeout() -> None:
    with contextlib.suppress(CallTimeout):
        time.sleep(30.0)
    first, second = ValueError("first"), ValueError("second")
    first.__cause__ = second
    second.__cause__ = first
    raise first


@pytest.mark.timeout(60)
def test_an_error_with_a_cause_cycle_after_the_timeout_still_returns() -> None:
    started = time.monotonic()
    with pytest.raises(ValueError, match="first"):
        run(_raises_a_cause_cycle_after_the_timeout, 0.1, mode="signal")
    assert time.monotonic() - started < 5.0


def test_no_arm_is_shorter_than_the_floor_toward_an_enclosing_timer_due_sooner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real = signal.setitimer
    stop: list[bool] = []
    calls: list[int] = []

    def enclosing(signum: int, frame: FrameType | None) -> None:
        calls.append(signum)
        if not stop:
            real(signal.ITIMER_REAL, 200e-6)  # re-arms itself well inside the floor

    signal.signal(signal.SIGALRM, enclosing)
    real(signal.ITIMER_REAL, 200e-6)
    delays = _record_setitimer(monkeypatch)
    try:
        with pytest.raises(CallTimeout):
            run(_targets.slow, 0.1, args=(5.0,), mode="signal")
    finally:
        stop.append(True)
        real(signal.ITIMER_REAL, 0)
    assert len(calls) >= 3
    # The last one gives the enclosing timer back its own schedule.
    assert all(delay == 0 or delay >= FLOOR for delay in delays[:-1]), delays


def test_an_early_tick_never_re_arms_for_less_than_the_floor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    signal.signal(signal.SIGALRM, lambda signum, frame: None)
    clock = _Clock()
    monkeypatch.setattr(_signal, "time", clock)
    signal.setitimer(signal.ITIMER_REAL, 10.0)
    enclosing_due = time.monotonic() + 10.0
    delays = _record_setitimer(monkeypatch)

    def stray_tick_just_before_the_enclosing_timer() -> str:
        clock.move_to(enclosing_due - 500e-6)
        signal.raise_signal(signal.SIGALRM)
        return "done"

    assert run(stray_tick_just_before_the_enclosing_timer, 30.0, mode="signal") == "done"
    rearms = delays[1:-1]
    assert any(delay > 0 for delay in rearms), delays
    assert all(delay == 0 or delay >= FLOOR for delay in rearms), delays


def test_a_tick_inside_the_last_millisecond_ends_the_call_without_re_arming(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    signal.signal(signal.SIGALRM, lambda signum, frame: None)
    clock = _Clock()
    monkeypatch.setattr(_signal, "time", clock)
    delays = _record_setitimer(monkeypatch)

    def stray_tick_inside_the_window() -> str:
        clock.move_to(clock.readings[0] + 30.0 - 500e-6)  # the call's start, plus its budget
        signal.raise_signal(signal.SIGALRM)
        time.sleep(5.0)
        return "missed"

    started = time.monotonic()
    with pytest.raises(CallTimeout):
        run(stray_tick_inside_the_window, 30.0, mode="signal")
    assert time.monotonic() - started < 2.0
    assert [delay for delay in delays[1:] if delay > 0] == [], delays
