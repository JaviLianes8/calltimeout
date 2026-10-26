"""A result that cannot come back gets the same bounded error as a call that cannot go."""

from __future__ import annotations

import pickle
import sys
import time
import traceback

import _result_targets
import _wire_targets
import pytest

from calltimeout import run

SENT_BACK = "the call's result cannot be sent back: "
REBUILT = "the call's result cannot be rebuilt in this process: "

# The whole printed chain: two short tracebacks, a cut text and ten cut notes.
PRINTED = 10_000


def _printed(error: BaseException) -> str:
    return "".join(traceback.format_exception(type(error), error, error.__traceback__))


def _sent_back_error(fn: object, *args: object) -> pickle.PicklingError:
    with pytest.raises(pickle.PicklingError) as info:
        run(fn, 60.0, args=args, mode="process")  # type: ignore[call-overload]
    return info.value


def _assert_message_quotes_at_most_60(error: BaseException, prefix: str) -> None:
    message = str(error)
    assert message.startswith(prefix), message
    assert len(message) <= len(prefix) + 63, message


def test_a_huge_error_about_a_result_is_quoted_briefly_and_chained_cut() -> None:
    error = _sent_back_error(_wire_targets.unpicklable_with_text, 200_000)
    _assert_message_quotes_at_most_60(error, SENT_BACK)
    assert error.__context__ is None
    assert len(_printed(error)) < PRINTED


def _notes_pickle_leaves(value: object) -> int:
    # Python 3.14 adds a note of its own (which item failed) to the 2,000 of the error.
    with pytest.raises(ValueError) as info:
        pickle.dumps((True, value, ""))
    return len(getattr(info.value, "__notes__", []))


@pytest.mark.skipif(sys.version_info < (3, 11), reason="traceback prints notes from 3.11")
def test_the_notes_of_an_error_about_a_result_are_bounded_and_counted() -> None:
    started = time.monotonic()
    notes = _notes_pickle_leaves(_result_targets.noted_unpicklable(2_000, 5_000))
    assert notes in (2_000, 2_001), notes
    error = _sent_back_error(_result_targets.noted_unpicklable, 2_000, 5_000)
    printed = _printed(error)
    assert len(printed) < PRINTED, len(printed)
    assert f"... and {notes - 10} more notes" in printed
    assert time.monotonic() - started < 30.0


def test_the_errors_chained_to_an_error_about_a_result_are_dropped() -> None:
    error = _sent_back_error(_result_targets.huge_unpicklable, 100_000)
    printed = _printed(error)
    assert len(printed) < PRINTED, len(printed)
    assert "w" * 61 not in printed


def test_a_deeply_nested_result_gets_a_bounded_error() -> None:
    error = _sent_back_error(_wire_targets.nested, 50_000)
    _assert_message_quotes_at_most_60(error, SENT_BACK)
    assert len(_printed(error)) < PRINTED


def test_a_huge_error_rebuilding_a_result_is_quoted_briefly_and_chained_cut() -> None:
    with pytest.raises(pickle.UnpicklingError) as info:
        run(_wire_targets.unrebuildable_with_text, 60.0, args=(200_000,), mode="process")
    error = info.value
    _assert_message_quotes_at_most_60(error, REBUILT)
    assert error.__context__ is None
    assert isinstance(error.__cause__, ValueError)
    assert len(str(error.__cause__)) == 303
    assert len(_printed(error)) < PRINTED
