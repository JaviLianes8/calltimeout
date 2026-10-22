"""Signal mode corner cases found by the mutation round: late, early and stray ticks.

Some tests drive the module's clock (``_signal.time``) to put a tick at an exact point of
the schedule; the timers and the handlers are real.
"""

from __future__ import annotations

import signal
import sys
import time
from types import FrameType, SimpleNamespace
from typing import Any

import _targets
import pytest

from calltimeout import CallTimeout, _signal, run

if sys.platform == "win32":
    pytest.skip("SIGALRM is POSIX", allow_module_level=True)


@pytest.fixture(autouse=True)
def _clean_timer() -> Any:
    yield
    signal.setitimer(signal.ITIMER_REAL, 0)
    signal.signal(signal.SIGALRM, signal.SIG_DFL)


def _clock(rate: float = 1.0) -> SimpleNamespace:
    """A monotonic clock running at rate times real speed, plus a settable jump."""
    base = time.monotonic()
    clock = SimpleNamespace(jump=0.0)
    clock.monotonic = lambda: base + (time.monotonic() - base) * rate + clock.jump
    return clock


def test_a_tick_pending_at_the_disarm_does_not_arm_the_timer_again(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real = signal.setitimer
    sent: list[bool] = []

    def setitimer(which: int, seconds: float, interval: float = 0.0) -> tuple[float, float]:
        previous = real(which, seconds, interval)
        if seconds == 0 and not sent:
            sent.append(True)
            signal.raise_signal(signal.SIGALRM)  # a tick that was already on its way
        return previous

    monkeypatch.setattr(signal, "setitimer", setitimer)
    assert run(_targets.echo, 30.0, args=(1,), mode="signal") == 1
    assert sent == [True]
    assert real(signal.ITIMER_REAL, 0) == (0.0, 0.0)


def test_a_tick_before_the_deadline_by_the_clock_arms_the_rest(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The clock runs at half speed, so the timer always fires "early": the handler must
    # keep re-arming for what is left until the clock reaches the deadline.
    monkeypatch.setattr(_signal, "time", _clock(rate=0.5))
    started = time.monotonic()
    with pytest.raises(CallTimeout):
        run(_targets.slow, 0.2, args=(10.0,), mode="signal")
    assert time.monotonic() - started < 5.0


def test_a_handler_that_overruns_the_deadline_still_ends_the_call() -> None:
    calls: list[int] = []

    def slow_outer(signum: int, frame: FrameType | None) -> None:
        calls.append(signum)
        time.sleep(0.5)  # past the inner deadline: the re-arm delay must not be zero

    signal.signal(signal.SIGALRM, slow_outer)
    signal.setitimer(signal.ITIMER_REAL, 0.05)
    started = time.monotonic()
    with pytest.raises(CallTimeout):
        run(_targets.slow, 0.2, args=(10.0,), mode="signal")
    assert time.monotonic() - started < 5.0
    assert calls == [signal.SIGALRM]


def test_a_stray_signal_once_the_outer_timer_is_due_passes_it_on_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[float] = []
    signal.signal(signal.SIGALRM, lambda signum, frame: calls.append(time.monotonic()))
    clock = _clock()
    monkeypatch.setattr(_signal, "time", clock)

    def stray_then_wait() -> str:
        time.sleep(0.05)
        clock.jump = 1.0  # by the clock the outer timer (0.5 s) is now due
        signal.raise_signal(signal.SIGALRM)
        time.sleep(0.8)  # past the real outer due time: no second delivery
        return "done"

    signal.setitimer(signal.ITIMER_REAL, 0.5)
    assert run(stray_then_wait, 5.0, mode="signal") == "done"
    assert len(calls) == 1
