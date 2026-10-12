"""Signal mode: SIGALRM interrupts the call in place (POSIX main thread only)."""

from __future__ import annotations

import signal
import sys
import threading
import time
from collections.abc import Callable
from types import FrameType

import _targets
import pytest

from calltimeout import CallTimeout, run

if sys.platform == "win32":
    pytest.skip("SIGALRM is POSIX", allow_module_level=True)


def test_returns_the_result_and_leaves_no_timer_armed() -> None:
    assert run(_targets.echo, 1.0, args=("ok",), mode="signal") == "ok"
    assert signal.getitimer(signal.ITIMER_REAL) == (0.0, 0.0)
    assert signal.getsignal(signal.SIGALRM) is signal.SIG_DFL


@pytest.mark.parametrize("target", [_targets.slow, _targets.spin])
def test_interrupts_a_sleep_and_a_pure_python_loop(target: Callable[[float], object]) -> None:
    started = time.monotonic()
    with pytest.raises(CallTimeout) as info:
        run(target, 0.1, args=(30.0,), mode="signal")
    assert time.monotonic() - started < 5.0
    assert info.value.timeout == 0.1
    assert isinstance(info.value.__cause__, CallTimeout)  # raised inside the call


def test_a_swallowed_timeout_still_ends_in_call_timeout() -> None:
    with pytest.raises(CallTimeout):
        run(_targets.swallows_timeout, 0.1, args=(30.0,), mode="signal")
    assert run(_targets.swallows_timeout, 0.1, args=(30.0,), mode="signal", default="d") == "d"


def test_returns_the_default_and_restores_the_previous_handler() -> None:
    def mine(signum: int, frame: FrameType | None) -> None:
        pass

    signal.signal(signal.SIGALRM, mine)
    try:
        assert run(_targets.slow, 0.1, args=(30.0,), mode="signal", default="d") == "d"
        assert signal.getsignal(signal.SIGALRM) is mine
    finally:
        signal.signal(signal.SIGALRM, signal.SIG_DFL)


def test_refuses_to_run_outside_the_main_thread() -> None:
    errors: list[BaseException] = []

    def worker() -> None:
        try:
            run(_targets.echo, 1.0, args=(1,), mode="signal")
        except BaseException as exc:
            errors.append(exc)

    thread = threading.Thread(target=worker)
    thread.start()
    thread.join()
    assert len(errors) == 1
    assert isinstance(errors[0], RuntimeError)


def _inner_call() -> str:
    return run(_targets.slow, 0.1, args=(30.0,), mode="signal", default="inner gave up")


def test_nested_calls_each_keep_their_own_budget() -> None:
    assert run(_inner_call, 5.0, mode="signal") == "inner gave up"
    with pytest.raises(CallTimeout) as info:
        run(
            run,
            0.1,
            args=(_targets.slow, 5.0),
            kwargs={"args": (30.0,), "mode": "signal"},
            mode="signal",
        )
    assert info.value.timeout == 0.1


def test_an_enclosing_timer_keeps_its_schedule() -> None:
    ticks: list[float] = []

    def tick(signum: int, frame: FrameType | None) -> None:
        ticks.append(time.monotonic())

    signal.signal(signal.SIGALRM, tick)
    try:
        started = time.monotonic()
        signal.setitimer(signal.ITIMER_REAL, 0.3)
        # The inner call finishes first; the outer alarm must still go off on time.
        assert run(_targets.slow, 1.0, args=(0.05,), mode="signal") == "done"
        assert ticks == []
        time.sleep(0.6)
        assert len(ticks) == 1
        assert 0.25 <= ticks[0] - started < 0.55
        # An outer timer due before the inner deadline still ticks during the call.
        signal.setitimer(signal.ITIMER_REAL, 0.05)
        assert run(_targets.slow, 2.0, args=(0.3,), mode="signal") == "done"
        assert len(ticks) == 2
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, signal.SIG_DFL)


def test_a_periodic_outer_timer_is_not_starved() -> None:
    ticks: list[float] = []
    signal.signal(signal.SIGALRM, lambda signum, frame: ticks.append(time.monotonic()))
    try:
        signal.setitimer(signal.ITIMER_REAL, 0.05, 0.05)
        with pytest.raises(CallTimeout):
            run(_targets.spin, 0.4, args=(30.0,), mode="signal")
        assert len(ticks) >= 4  # the outer timer kept ticking during the call
        before = len(ticks)
        time.sleep(0.3)
        assert len(ticks) > before  # and after it
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, signal.SIG_DFL)
