import threading
import time

import pytest

from calltimeout import CallTimeout, run

# Targets live at module level so the spawn start method can import and pickle them.
_gate = threading.Event()


def _blocks_until_gate() -> str:
    _gate.wait()
    return "released"


def _echo(value: object) -> object:
    return value


def _slow(seconds: float) -> str:
    time.sleep(seconds)
    return "done"


def _boom() -> None:
    raise ValueError("boom")


def test_returns_the_value_when_the_call_finishes_in_time() -> None:
    assert run(_echo, 1.0, args=("ok",)) == "ok"


def test_passes_keyword_arguments_to_the_call() -> None:
    assert run(_echo, 1.0, kwargs={"value": 7}) == 7


def test_raises_call_timeout_when_the_thread_call_overruns() -> None:
    _gate.clear()
    try:
        with pytest.raises(CallTimeout):
            run(_blocks_until_gate, 0.05)
    finally:
        _gate.set()


def test_returns_the_default_on_timeout_instead_of_raising() -> None:
    _gate.clear()
    try:
        assert run(_blocks_until_gate, 0.05, default="fallback") == "fallback"
    finally:
        _gate.set()


def test_propagates_an_exception_raised_by_the_call() -> None:
    with pytest.raises(ValueError, match="boom"):
        run(_boom, 1.0)


def test_the_timeout_carries_the_budget_that_was_exceeded() -> None:
    _gate.clear()
    try:
        with pytest.raises(CallTimeout) as info:
            run(_blocks_until_gate, 0.05)
        assert info.value.timeout == 0.05
    finally:
        _gate.set()


def test_call_timeout_is_a_timeout_error() -> None:
    assert issubclass(CallTimeout, TimeoutError)


def test_process_mode_returns_the_result() -> None:
    assert run(_echo, 5.0, args=(42,), mode="process") == 42


def test_process_mode_terminates_and_times_out() -> None:
    with pytest.raises(CallTimeout):
        run(_slow, 0.1, args=(5.0,), mode="process")


def test_process_mode_returns_the_default_on_timeout() -> None:
    assert run(_slow, 0.1, args=(5.0,), mode="process", default="gave_up") == "gave_up"


def test_rejects_an_unknown_mode() -> None:
    with pytest.raises(ValueError, match="unknown mode"):
        run(_echo, 1.0, args=("x",), mode="bogus")  # type: ignore[call-overload]


def test_rejects_a_negative_timeout() -> None:
    with pytest.raises(ValueError, match="negative"):
        run(_echo, -1.0, args=("x",))
