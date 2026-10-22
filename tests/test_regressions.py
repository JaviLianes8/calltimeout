"""Regression tests for problems found in review."""

from __future__ import annotations

import multiprocessing
import os
import pickle
import sys
from pathlib import Path

import _targets
import pytest

from calltimeout import CallTimeout, Mode, _process, run, with_timeout

MODES: list[Mode] = ["thread", "process"]
if sys.platform != "win32":
    MODES.append("signal")


def test_process_mode_accepts_queues_and_locks_as_arguments() -> None:
    queue: multiprocessing.Queue[str] = multiprocessing.Queue()
    lock = multiprocessing.Lock()
    assert run(_targets.put_in_queue, 30.0, args=(queue, lock), mode="process") == "put"
    assert queue.get(timeout=5) == "sent"


def test_a_finished_child_is_left_to_shut_down_on_its_own(tmp_path: Path) -> None:
    marker = tmp_path / "marker"
    assert run(_targets.write_later, 30.0, args=(str(marker),), mode="process") == "returned"
    assert marker.read_text(encoding="utf-8") == "flushed"


def test_an_interrupt_during_the_grace_period_still_ends_the_child(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def interrupted(process: object, seconds: float) -> bool:
        raise KeyboardInterrupt

    monkeypatch.setattr(_process, "_exits_within", interrupted)
    with pytest.raises(KeyboardInterrupt):
        run(_targets.slow, 0.5, args=(30.0,), mode="process")
    assert multiprocessing.active_children() == []


def test_a_result_the_parent_cannot_rebuild_is_a_clear_error() -> None:
    with pytest.raises(pickle.UnpicklingError, match="cannot be rebuilt") as info:
        run(_targets.child_only_result, 30.0, mode="process")
    assert isinstance(info.value.__cause__, ModuleNotFoundError)


def test_the_decorator_works_when_assigned_to_another_name() -> None:
    assert _targets.assigned_pid() != os.getpid()


@pytest.mark.parametrize("mode", MODES)
def test_a_zero_budget_never_starts_the_call_in_any_process(mode: Mode, tmp_path: Path) -> None:
    marker = tmp_path / "marker"
    with pytest.raises(CallTimeout):
        run(_targets.touch, 0, args=(str(marker),), mode=mode)
    assert not marker.exists()
    run(_targets.touch, 30.0, args=(str(marker),), mode=mode)
    assert marker.exists()  # the same call with a budget does leave the marker


def test_a_huge_integer_timeout_is_a_value_error() -> None:
    with pytest.raises(ValueError, match="at most"):
        run(_targets.echo, 10**400, args=(1,))


def test_the_decorator_rejects_a_mode_that_is_not_a_str_like_run() -> None:
    with pytest.raises(TypeError, match="mode must be a str, not list"):
        with_timeout(1.0, mode=["thread"])  # type: ignore[call-overload]
    with pytest.raises(TypeError, match="mode must be a str, not list"):
        run(_targets.echo, 1.0, args=(1,), mode=["thread"])  # type: ignore[call-overload]


def test_kwargs_must_be_a_mapping() -> None:
    with pytest.raises(TypeError, match="kwargs must be a mapping"):
        run(dict, 1.0, kwargs="ab")  # type: ignore[call-overload]


def test_the_timeout_is_reported_as_the_validated_float() -> None:
    with pytest.raises(CallTimeout) as info:
        run(_targets.echo, -0.0, args=(1,))
    assert str(info.value) == "call did not finish within 0.0 seconds"
