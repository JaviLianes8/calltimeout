"""Process mode: the details of the bounded cause of a call that cannot be sent."""

from __future__ import annotations

import multiprocessing
import pickle
import sys
import traceback

import _hostile_errors
import _wire_targets
import pytest

from calltimeout import run

pytestmark = pytest.mark.skipif(
    multiprocessing.get_start_method() == "fork", reason="fork pickles nothing"
)

SENT = "the call cannot be sent to the child process"


def _cause(error: Exception) -> BaseException:
    bad = _wire_targets.RaisesOnReduce(error)
    with pytest.raises(pickle.PicklingError, match=SENT) as info:
        run(_wire_targets.count, 30.0, args=(bad,), mode="process")
    cause = info.value.__cause__
    assert cause is not None
    return cause


def test_the_message_quotes_the_repr_of_pickles_error() -> None:
    bad = _wire_targets.RaisesOnReduce(TypeError("boom"))
    with pytest.raises(pickle.PicklingError) as info:
        run(_wire_targets.count, 30.0, args=(bad,), mode="process")
    assert str(info.value) == f"{SENT}: TypeError('boom')"


def test_a_plain_error_whose_argument_has_no_str_is_cut_in_place() -> None:
    cause = _cause(TypeError(_hostile_errors.BadStrArg()))
    assert type(cause) is TypeError
    assert cause.args == ("<str() failed>",)


def test_the_stand_in_keeps_the_frames_where_the_argument_failed() -> None:
    cause = _cause(_hostile_errors.ReadOnlyArgs())
    assert type(cause) is RuntimeError
    frames = traceback.extract_tb(cause.__traceback__)
    raising = [frame for frame in frames if frame.filename.endswith("_wire_targets.py")]
    assert [frame.name for frame in raising][-1:] == ["__reduce__"], frames


def test_ten_notes_are_kept_and_the_rest_counted() -> None:
    notes = [f"note {index}" for index in range(15)]
    cause = _cause(_hostile_errors.with_notes(notes))
    every = len(notes)  # pickle may have added its own notes to the list
    expected = [f"note {index}" for index in range(10)]
    assert vars(cause)["__notes__"] == [*expected, f"... and {every - 10} more notes"]


def _keeps_odd_notes() -> bool:
    """False where pickle, adding its own note, replaces an error whose notes are a str."""
    error = _hostile_errors.with_notes("S")
    try:
        pickle.dumps([_wire_targets.RaisesOnReduce(error)])
    except Exception as raised:
        return raised is error
    return False


@pytest.mark.skipif(not _keeps_odd_notes(), reason="pickle replaces such an error here")
def test_notes_set_to_a_str_are_kept_as_one_cut_note() -> None:
    cause = _cause(_hostile_errors.with_notes("S" * 1000))
    assert vars(cause)["__notes__"] == ["S" * 60 + "..."]


@pytest.mark.parametrize("notes", [None, []], ids=["no notes", "empty notes"])
def test_a_cause_without_notes_gets_none_and_takes_new_ones(notes: list[str] | None) -> None:
    error = TypeError("plain") if notes is None else _hostile_errors.with_notes(notes)
    cause = _cause(error)
    own = vars(cause)
    assert "__notes__" not in own or own["__notes__"], own  # never None or an empty list
    if sys.version_info >= (3, 11):
        cause.add_note("added")
        assert vars(cause)["__notes__"][-1] == "added"
