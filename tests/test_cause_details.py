"""Process mode: the details of the bounded cause of a call that cannot be sent."""

from __future__ import annotations

import multiprocessing
import pickle
import sys

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


def test_the_message_names_only_a_safe_error_category() -> None:
    bad = _wire_targets.RaisesOnReduce(TypeError("boom"))
    with pytest.raises(pickle.PicklingError) as info:
        run(_wire_targets.count, 30.0, args=(bad,), mode="process")
    assert str(info.value) == f"{SENT}: TypeError"


def test_a_plain_error_whose_argument_has_no_str_is_replaced() -> None:
    cause = _cause(TypeError(_hostile_errors.BadStrArg()))
    assert type(cause) is TypeError
    assert cause.args == ("transport operation failed",)


def test_the_stand_in_discards_caller_frames() -> None:
    cause = _cause(_hostile_errors.ReadOnlyArgs())
    assert type(cause) is RuntimeError
    assert cause.__traceback__ is None


def test_all_notes_are_discarded() -> None:
    notes = [f"note {index}" for index in range(15)]
    cause = _cause(_hostile_errors.with_notes(notes))
    assert "__notes__" not in vars(cause)


def _keeps_odd_notes() -> bool:
    """False where pickle, adding its own note, replaces an error whose notes are a str."""
    error = _hostile_errors.with_notes("S")
    try:
        pickle.dumps([_wire_targets.RaisesOnReduce(error)])
    except Exception as raised:
        return raised is error
    return False


@pytest.mark.skipif(not _keeps_odd_notes(), reason="pickle replaces such an error here")
def test_notes_set_to_a_str_are_discarded() -> None:
    cause = _cause(_hostile_errors.with_notes("S" * 1000))
    assert "__notes__" not in vars(cause)


@pytest.mark.parametrize(
    "notes",
    [None, [], _hostile_errors.NoteList(["a", "b"]), _hostile_errors.NoteList()],
    ids=["no notes", "empty notes", "notes in a list subclass", "empty list subclass"],
)
def test_a_cause_without_notes_gets_none_and_takes_new_ones(notes: list[str] | None) -> None:
    # Notes held in a list subclass are dropped, never left as None: add_note() needs a list.
    error = TypeError("plain") if notes is None else _hostile_errors.with_notes(notes)
    cause = _cause(error)
    own = vars(cause)
    assert "__notes__" not in own or own["__notes__"], own  # never None or an empty list
    if sys.version_info >= (3, 11):
        cause.add_note("added")
        assert vars(cause)["__notes__"][-1] == "added"
