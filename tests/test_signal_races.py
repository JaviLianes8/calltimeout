"""Signal mode: enclosing ticks that race with the start of a call, and timers over many calls.

The races are made exact by taking a tick at the worst moment (right after the call puts its
handler in place); the timers, handlers and the schedules measured are real.
"""

from __future__ import annotations

import contextlib
import itertools
import signal
import sys
import time
from collections.abc import Callable
from types import FrameType, SimpleNamespace
from typing import Any

import pytest

from calltimeout import CallTimeout, _signal, run

if sys.platform == "win32":
    pytest.skip("SIGALRM is POSIX", allow_module_level=True)

INTERVAL = 0.01


@pytest.fixture(autouse=True)
def _clean_timer() -> Any:
    yield
    signal.setitimer(signal.ITIMER_REAL, 0)
    signal.signal(signal.SIGALRM, signal.SIG_DFL)


def _tick_when_installed(monkeypatch: pytest.MonkeyPatch, before: Callable[[], None]) -> None:
    """Take a SIGALRM the moment the next call puts its own handler in place, after before()."""
    real = signal.signal
    done: list[bool] = []

    def install(signum: int, handler: Any) -> Any:
        old = real(signum, handler)
        if not done:  # only the first: the call's own handler
            done.append(True)
            before()
            signal.raise_signal(signal.SIGALRM)
        return old

    monkeypatch.setattr(signal, "signal", install)


def test_a_tick_on_its_way_as_the_call_starts_reaches_the_enclosing_handler(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ticks: list[int] = []

    def mine(signum: int, frame: FrameType | None) -> None:
        ticks.append(signum)

    signal.signal(signal.SIGALRM, mine)
    signal.setitimer(signal.ITIMER_REAL, 30.0, 30.0)
    _tick_when_installed(monkeypatch, lambda: None)
    assert run(int, 5.0, args=("7",), mode="signal") == 7
    monkeypatch.undo()
    assert ticks == [signal.SIGALRM]
    assert signal.getsignal(signal.SIGALRM) is mine
    delay, interval = signal.getitimer(signal.ITIMER_REAL)
    assert 29.0 < delay <= 30.0
    assert interval == pytest.approx(30.0)


def test_an_outer_deadline_due_as_an_inner_call_starts_is_not_lost(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The outer call's one-shot timer fires just as the inner call starts: the inner call
    # reads no timer left, and the tick reaches its handler. It must end the outer call.
    base = time.monotonic()
    clock = SimpleNamespace(jump=0.0)
    clock.monotonic = lambda: time.monotonic() + clock.jump
    monkeypatch.setattr(_signal, "time", clock)

    def outer_timer_fires() -> None:
        signal.setitimer(signal.ITIMER_REAL, 0)
        clock.jump = base + 1.0 - time.monotonic()  # the outer budget (0.5 s) is over

    def attempt() -> int:
        _tick_when_installed(monkeypatch, outer_timer_fires)
        return run(int, 5.0, args=("7",), mode="signal")

    started = time.monotonic()
    with pytest.raises(CallTimeout) as info:
        run(attempt, 0.5, mode="signal")
    assert info.value.timeout == 0.5
    assert time.monotonic() - started < 2.0


def test_many_quick_calls_under_a_fast_enclosing_timer_keep_its_handler() -> None:
    ticks: list[float] = []
    signal.signal(signal.SIGALRM, lambda signum, frame: ticks.append(time.monotonic()))
    signal.setitimer(signal.ITIMER_REAL, 0.001, 0.001)
    stop = time.monotonic() + 0.5
    while time.monotonic() < stop:
        assert run(int, 1.0, args=("7",), mode="signal") == 7
    seen = len(ticks)
    time.sleep(0.2)
    assert len(ticks) - seen > 50  # the timer still runs and reaches its own handler
    assert seen > 250


def _under_interval_timer(work: Callable[[], None]) -> list[float]:
    """Run work under a 10 ms interval timer; the time of each tick from its start."""
    ticks: list[float] = []
    signal.signal(signal.SIGALRM, lambda signum, frame: ticks.append(time.monotonic()))
    start = time.monotonic()
    signal.setitimer(signal.ITIMER_REAL, INTERVAL, INTERVAL)
    work()
    signal.setitimer(signal.ITIMER_REAL, 0)
    return [tick - start for tick in ticks]


def _calls_for(seconds: float, budget: float, nap: float) -> Callable[[], None]:
    def work() -> None:
        stop = time.monotonic() + seconds
        while time.monotonic() < stop:
            with contextlib.suppress(CallTimeout):
                run(time.sleep, budget, args=(nap,), mode="signal")

    return work


@pytest.mark.parametrize(
    ("budget", "nap"), [(0.002, 0.003), (0.5, 0.003), (1.0, 0.0)], ids=["over", "in", "quick"]
)
def test_an_interval_timer_keeps_every_tick_on_schedule_over_many_calls(
    budget: float, nap: float
) -> None:
    ticks = _under_interval_timer(_calls_for(2.0, budget, nap))
    assert len(ticks) >= int(2.0 / INTERVAL) - 1  # none lost
    gaps = [later - earlier for earlier, later in itertools.pairwise(ticks)]
    assert min(gaps) > INTERVAL / 2  # none delivered twice
    # Up to 1 ms late each (the floor), and that lateness never adds up.
    assert max(tick - INTERVAL * (n + 1) for n, tick in enumerate(ticks)) < 0.004


def test_a_one_shot_timer_fires_on_time_across_many_quick_calls() -> None:
    fired: list[float] = []
    signal.signal(signal.SIGALRM, lambda signum, frame: fired.append(time.monotonic()))
    start = time.monotonic()
    signal.setitimer(signal.ITIMER_REAL, 0.5)
    while not fired and time.monotonic() - start < 5.0:
        run(int, 5.0, args=("1",), mode="signal")
    assert fired
    assert 0.5 - 0.0005 <= fired[0] - start <= 0.5 + 0.003
