"""Promises added for 1.0.0: bounded messages, stable exception names, process budget."""

from __future__ import annotations

import multiprocessing
import pickle
import sys
import time
import types
from pathlib import Path

import _targets
import pytest

from calltimeout import CallCrashed, CallTimeout, _process, _wire, run, with_timeout

needs_pickling = pytest.mark.skipif(
    multiprocessing.get_start_method() == "fork", reason="fork pickles nothing"
)


@pytest.mark.parametrize("error", [CallTimeout(1.0), CallCrashed(2)])
def test_the_exceptions_are_named_after_the_package(error: Exception) -> None:
    assert type(error).__module__ == "calltimeout"
    data = pickle.dumps(error)
    assert b"calltimeout._errors" not in data
    assert b"calltimeout" in data


@pytest.mark.parametrize("error", [CallTimeout(1.0), CallCrashed(2)])
def test_extra_attributes_and_notes_survive_pickle(error: Exception) -> None:
    error.extra = "kept"  # type: ignore[attr-defined]
    if sys.version_info >= (3, 11):
        error.add_note("a note")
    clone = pickle.loads(pickle.dumps(error))
    assert clone.extra == "kept"
    if sys.version_info >= (3, 11):
        assert clone.__notes__ == ["a note"]


def test_a_huge_integer_is_described_not_printed() -> None:
    assert str(CallTimeout(2**200)) == "call did not finish within an integer of 201 bits seconds"
    assert str(CallCrashed(2**64)) == (
        "the call's process exited with code an integer of 65 bits before returning"
    )
    assert str(CallCrashed(2**63)) == (
        "the call's process exited with code 9223372036854775808 before returning"
    )


def test_an_unknown_mode_is_quoted_briefly_and_the_names_are_listed() -> None:
    with pytest.raises(ValueError) as info:
        run(_targets.echo, 1.0, args=(1,), mode="x" * 10_000)  # type: ignore[call-overload]
    message = str(info.value)
    assert message == (
        f"unknown mode '{'x' * 59}...: expected one of 'thread', 'process', 'signal'"
    )


def test_a_long_type_name_is_cut_in_messages() -> None:
    long_type = type("T" * 500, (), {})
    with pytest.raises(TypeError) as info:
        run(_targets.echo, long_type())
    assert str(info.value) == f"timeout must be a number of seconds, not {'T' * 60}..."


def test_a_str_subclass_mode_is_read_as_the_plain_name() -> None:
    class Odd(str):
        def __eq__(self, other: object) -> bool:
            return False

        def __hash__(self) -> int:
            return 0

    assert run(_targets.echo, 30.0, args=(1,), mode=Odd("thread")) == 1  # type: ignore[call-overload]
    decorated = with_timeout(30.0, mode=Odd("process"))(_targets.pid)  # type: ignore[call-overload]
    assert callable(decorated)


def test_the_coroutine_hint_names_a_tool_every_supported_python_has() -> None:
    async def job() -> None:
        return None

    with pytest.raises(TypeError, match=r"asyncio\.wait_for\(\)"):
        _ = run(job, 1.0)


@needs_pickling
def test_pickling_that_spends_the_budget_never_starts_the_child(tmp_path: Path) -> None:
    marker = tmp_path / "marker"
    with pytest.raises(CallTimeout):
        run(_targets.touch_with, 0.3, args=(str(marker), _targets.SlowToPickle()), mode="process")
    assert not marker.exists()
    assert multiprocessing.active_children() == []


@needs_pickling
def test_a_call_the_child_cannot_load_reports_the_real_error() -> None:
    module = types.ModuleType("calltimeout_parent_only")
    exec("def hidden():\n    return 1\n", module.__dict__)
    sys.modules[module.__name__] = module
    try:
        with pytest.raises(ModuleNotFoundError, match="calltimeout_parent_only") as info:
            run(module.hidden, 30.0, mode="process")
    finally:
        del sys.modules[module.__name__]
    assert "pickle.loads" in str(info.value.__cause__)


def test_an_unpicklable_result_carries_the_childs_traceback_of_the_failure() -> None:
    with pytest.raises(pickle.PicklingError) as info:
        run(_targets.unpicklable_result, 30.0, mode="process")
    assert "lock" in str(info.value)
    trace = str(info.value.__cause__)
    assert isinstance(info.value.__cause__, _wire.RemoteTraceback)
    assert "TypeError" in trace
    assert "direct cause" in trace


def test_a_reader_cut_short_counts_as_no_result() -> None:
    class Broken:
        def poll(self) -> bool:
            return True

        def recv_bytes(self) -> bytes:
            raise OSError("pipe broke")

    assert _process._receive(Broken(), []) is None


def test_waiting_for_a_lost_childs_exit_stays_within_the_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The pipe reports no result while the child is still running: the exit code is
    # waited for only until the deadline, then it is a timeout, not a 30 second hang.
    monkeypatch.setattr(_process, "_receive", lambda reader, ready: None)
    monkeypatch.setattr(_process, "_await", lambda reader, process, deadline: [reader])
    started = time.monotonic()
    with pytest.raises(CallTimeout):
        run(_targets.slow, 1.0, args=(30.0,), mode="process")
    assert time.monotonic() - started < 10.0
    assert multiprocessing.active_children() == []
