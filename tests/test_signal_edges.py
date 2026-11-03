"""Signal mode corner cases found by the mutation round: late, early and stray ticks.

Some tests drive the module's clock (``_signal.time``) to put a tick at an exact point of
the schedule; the timers and the handlers are real.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path
from types import FrameType, SimpleNamespace
from typing import Any

import _targets
import pytest

import calltimeout
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


def _record_setitimer(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    real = signal.setitimer
    delays: list[float] = []

    def setitimer(which: int, seconds: float, interval: float = 0.0) -> tuple[float, float]:
        delays.append(seconds)
        return real(which, seconds, interval)

    monkeypatch.setattr(signal, "setitimer", setitimer)
    return delays


def test_the_handler_never_re_arms_for_less_than_a_millisecond(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A shorter re-arm can fire after the handler returns but before the interrupted
    # sleep blocks again: that tick is lost and the call overruns by its whole sleep.
    monkeypatch.setattr(_signal, "time", _clock(rate=0.5))
    delays = _record_setitimer(monkeypatch)
    with pytest.raises(CallTimeout):
        run(_targets.slow, 0.2, args=(10.0,), mode="signal")
    rearms = [delay for delay in delays[1:] if delay > 0]
    assert len(rearms) >= 3, delays
    assert min(rearms) >= 1e-3, delays


def test_an_outer_tick_just_before_the_deadline_ends_the_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    signal.signal(signal.SIGALRM, lambda signum, frame: None)
    signal.setitimer(signal.ITIMER_REAL, 0.1)
    delays = _record_setitimer(monkeypatch)
    started = time.monotonic()
    with pytest.raises(CallTimeout):
        run(_targets.slow, 0.1 + 200e-6, args=(5.0,), mode="signal")
    assert time.monotonic() - started < 2.0
    # The first arms the call and the last disarms it or gives back the outer timer.
    assert all(delay == 0 or delay >= 1e-3 for delay in delays[1:-1]), delays


def _cleanup_with_its_own_cause() -> None:
    try:
        time.sleep(30.0)
    except CallTimeout:
        raise ValueError("cleanup") from KeyError("detail")


def test_an_error_raised_from_another_cause_while_handling_the_timeout_counts_as_it() -> None:
    assert run(_cleanup_with_its_own_cause, 0.1, mode="signal", default="fallback") == "fallback"
    with pytest.raises(CallTimeout):
        run(_cleanup_with_its_own_cause, 0.1, mode="signal")


def test_an_enclosing_timer_with_the_default_action_still_ends_the_process() -> None:
    code = (
        "import signal, time\n"
        "from calltimeout import run\n"
        "signal.setitimer(signal.ITIMER_REAL, 0.3)\n"
        "run(time.sleep, 5.0, args=(2.0,), mode='signal')\n"
        "print('survived')\n"
    )
    path = str(Path(calltimeout.__file__).resolve().parents[1])
    env = {**os.environ, "PYTHONPATH": path}
    done = subprocess.run(
        [sys.executable, "-c", code], env=env, capture_output=True, text=True, timeout=60
    )
    assert done.returncode == -signal.SIGALRM, (done.returncode, done.stdout, done.stderr)
    assert "survived" not in done.stdout


def test_a_zero_budget_off_the_main_thread_still_reports_the_misuse() -> None:
    errors: list[BaseException] = []

    def worker() -> None:
        try:
            run(len, 0, args=("x",), mode="signal")
        except BaseException as exc:
            errors.append(exc)

    thread = threading.Thread(target=worker)
    thread.start()
    thread.join()
    assert [type(error) for error in errors] == [RuntimeError]
