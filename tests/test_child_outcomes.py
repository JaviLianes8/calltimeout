"""Process mode: what comes back from the child when the call is odd, stalls or nests."""

from __future__ import annotations

import multiprocessing
import os
import pickle
import sys
import time

import _child_targets
import pytest

from calltimeout import CallTimeout, RemoteTraceback, _process, run

FORK = multiprocessing.get_start_method() == "fork"

LOADED = "the call cannot be loaded in the child process: "


@pytest.mark.parametrize(
    "target", [_child_targets.raise_rebuilt_as_text, _child_targets.raise_rebuilt_as_object]
)
def test_a_child_error_that_rebuilds_as_something_else_arrives_as_a_stand_in(
    target: object,
) -> None:
    with pytest.raises(RuntimeError) as info:
        run(target, 30.0, mode="process")  # type: ignore[call-overload]
    message = str(info.value)
    assert message.startswith("_child_targets.RebuiltAs"), message
    assert ": the real error (not picklable: TypeError('it rebuilds as " in message
    assert isinstance(info.value.__cause__, RemoteTraceback)
    assert "the real error" in str(info.value.__cause__)  # the child's own traceback


def test_a_stand_in_names_the_type_by_module_and_qualname_even_if_name_is_refused() -> None:
    with pytest.raises(RuntimeError) as info:
        run(_child_targets.raise_unpicklable, 30.0, mode="process")
    message = str(info.value)
    assert message.startswith("_child_targets.Unpicklable: boom (not picklable: "), message


@pytest.mark.skipif(FORK, reason="fork pickles nothing on the way in")
def test_a_function_the_child_cannot_find_raises_a_bounded_unpickling_error() -> None:
    name = "only_in_the_caller_" + "x" * 1_000_000

    def work() -> int:
        return 7

    work.__module__ = "_child_targets"
    work.__qualname__ = work.__name__ = name
    setattr(_child_targets, name, work)  # found here when pickled, absent in the child
    try:
        with pytest.raises(pickle.UnpicklingError) as info:
            run(work, 30.0, mode="process")
    finally:
        delattr(_child_targets, name)
    message = str(info.value)
    assert message.startswith(LOADED + "AttributeError("), message
    assert len(message) <= len(LOADED) + 63
    assert isinstance(info.value.__cause__, RemoteTraceback)
    assert len(str(info.value.__cause__)) < 5_000
    assert "only_in_the_caller_xxx" in str(info.value.__cause__)


@pytest.mark.skipif(FORK, reason="fork pickles nothing on the way in")
def test_an_argument_that_fails_to_rebuild_in_the_child_raises_a_bounded_unpickling_error() -> None:
    with pytest.raises(pickle.UnpicklingError) as info:
        run(len, 30.0, args=(_child_targets.LoadsBadly(1_000_000),), mode="process")
    message = str(info.value)
    assert message.startswith(LOADED), message
    assert len(message) <= len(LOADED) + 63
    assert "KeyError" in str(info.value.__cause__)
    assert len(str(info.value.__cause__)) < 5_000


@pytest.mark.skipif(sys.platform == "win32", reason="Windows writes a result in one piece")
@pytest.mark.parametrize("stop", [False, True], ids=["asleep", "stopped"])
def test_a_child_that_stalls_while_sending_its_result_still_ends_at_the_deadline(
    stop: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(_process, "GRACE", 0.5)
    started = time.monotonic()
    with pytest.raises(CallTimeout) as info:
        run(_child_targets.stall_after_header, 1.0, args=(stop,), mode="process")
    elapsed = time.monotonic() - started
    assert info.value.timeout == 1.0
    # Terminated at the deadline; a stopped child ignores that, and is killed after GRACE.
    assert elapsed < 1.3 if not stop else 1.5 <= elapsed < 2.0, elapsed
    assert multiprocessing.active_children() == []


def test_a_decorated_call_inside_another_calls_child_gets_its_own_child_and_budget() -> None:
    caller, inner = run(_child_targets.outer, 30.0, mode="process")
    assert len({os.getpid(), caller, inner}) == 3
    started = time.monotonic()
    assert run(_child_targets.outer_slow, 30.0, mode="process") == "CallTimeout"
    assert time.monotonic() - started < 4.0


def test_a_classmethod_sent_through_its_class_names_the_child_after_the_method() -> None:
    assert _child_targets.Owner.name() == "calltimeout:Owner.name"
