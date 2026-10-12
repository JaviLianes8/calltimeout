"""Process mode: the child really stops, and a crash is not a timeout."""

from __future__ import annotations

import multiprocessing
import os
import pickle
import sys
import time
from pathlib import Path

import _targets
import pytest

from calltimeout import CallCrashed, CallTimeout, _process, _wire, run

posix_only = pytest.mark.skipif(sys.platform == "win32", reason="SIGTERM is POSIX")


def _no_children_left() -> bool:
    return multiprocessing.active_children() == []


def test_returns_the_result_from_another_process() -> None:
    assert run(_targets.pid, 30.0, mode="process") != os.getpid()
    assert run(_targets.echo, 30.0, args=(42,), mode="process") == 42
    assert _no_children_left()


def test_passes_keyword_arguments() -> None:
    assert run(_targets.echo, 30.0, kwargs={"value": "kw"}, mode="process") == "kw"


def test_overrun_raises_and_leaves_no_child_behind() -> None:
    with pytest.raises(CallTimeout) as info:
        run(_targets.slow, 0.5, args=(30.0,), mode="process")
    assert info.value.timeout == 0.5
    assert _no_children_left()


def test_overrun_returns_the_default() -> None:
    assert run(_targets.slow, 0.5, args=(30.0,), mode="process", default="gave up") == "gave up"


def test_an_exception_comes_back_with_the_childs_traceback() -> None:
    with pytest.raises(ValueError, match="boom") as info:
        run(_targets.boom, 30.0, mode="process")
    cause = info.value.__cause__
    assert isinstance(cause, _wire.RemoteTraceback)
    assert 'raise ValueError("boom")' in str(cause)


def test_a_child_that_dies_is_reported_at_once_as_a_crash() -> None:
    started = time.monotonic()
    with pytest.raises(CallCrashed) as info:
        run(_targets.hard_exit, 30.0, args=(3,), mode="process")
    assert info.value.exitcode == 3
    assert time.monotonic() - started < 15.0  # not the 30 second budget
    assert _no_children_left()


def test_a_crash_is_not_answered_with_the_default() -> None:
    with pytest.raises(CallCrashed):
        run(_targets.hard_exit, 30.0, args=(4,), mode="process", default="nope")


def test_an_unpicklable_result_is_a_clear_error_not_a_timeout() -> None:
    started = time.monotonic()
    with pytest.raises(pickle.PicklingError, match="cannot be sent back"):
        run(_targets.unpicklable_result, 30.0, mode="process")
    assert time.monotonic() - started < 15.0


def test_an_exception_that_cannot_be_rebuilt_arrives_as_a_stand_in() -> None:
    with pytest.raises(RuntimeError, match="LocalOnlyError: a-b") as info:
        run(_targets.raises_unrebuildable, 30.0, mode="process")
    assert "raise LocalOnlyError" in str(info.value.__cause__)


def test_an_exception_that_cannot_be_pickled_arrives_as_a_stand_in() -> None:
    with pytest.raises(RuntimeError, match="ValueError: carries a lock"):
        run(_targets.raises_unpicklable, 30.0, mode="process")


def test_an_interrupted_wait_still_stops_the_child(monkeypatch: pytest.MonkeyPatch) -> None:
    def interrupted(objects: object, timeout: object) -> list[object]:
        raise KeyboardInterrupt

    monkeypatch.setattr(_process, "wait", interrupted)
    with pytest.raises(KeyboardInterrupt):
        run(_targets.slow, 30.0, args=(30.0,), mode="process")
    assert _no_children_left()


@posix_only
def test_a_child_that_ignores_sigterm_is_killed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(_process, "GRACE", 0.2)
    started = time.monotonic()
    with pytest.raises(CallTimeout):
        run(_targets.ignores_sigterm, 2.0, args=(60.0,), mode="process")
    assert time.monotonic() - started < 20.0
    assert _no_children_left()


@posix_only
def test_a_terminated_child_gets_a_grace_period_to_clean_up(tmp_path: Path) -> None:
    marker = tmp_path / "marker"
    with pytest.raises(CallTimeout):
        run(_targets.cleans_up_on_sigterm, 2.0, args=(str(marker), 60.0), mode="process")
    assert marker.read_text(encoding="utf-8") == "cleaned up"


@posix_only
def test_a_crash_is_seen_even_while_a_grandchild_holds_the_pipe() -> None:
    started = time.monotonic()
    with pytest.raises(CallCrashed) as info:
        run(_targets.crash_leaving_grandchild, 30.0, args=(8.0,), mode="process")
    assert info.value.exitcode == 5
    assert time.monotonic() - started < 6.0


def test_an_unpicklable_callable_fails_before_waiting() -> None:
    if multiprocessing.get_start_method() == "fork":
        pytest.skip("fork copies the callable instead of pickling it")
    with pytest.raises((pickle.PicklingError, AttributeError, TypeError)):
        run(lambda: 1, 30.0, mode="process")
    assert _no_children_left()
    # A start that failed half way once made the next child answer on a stale pipe.
    assert [run(_targets.echo, 30.0, args=(n,), mode="process") for n in (1, 2)] == [1, 2]


def test_a_nested_process_timeout_propagates_through_the_default() -> None:
    with pytest.raises(CallTimeout) as info:
        run(_targets.nested_timeout, 60.0, mode="process", default="outer default")
    assert info.value.timeout == 0.05
