"""Process mode: no shape of pickle error makes the traceback of a call that cannot be sent huge."""

from __future__ import annotations

import multiprocessing
import pickle
import sys
import traceback
from collections.abc import Callable

import _hostile_errors
import _targets
import _wire_targets
import pytest

from calltimeout import run

needs_pickling = pytest.mark.skipif(
    multiprocessing.get_start_method() == "fork", reason="fork pickles nothing"
)

SENT = "the call cannot be sent to the child process"

HUGE = "SECRET-" + "H" * 100_000

HOSTILE: dict[str, Callable[[], Exception]] = {
    "type that cannot be named": _hostile_errors.QualErr,
    "str that lies about its length": _hostile_errors.LyingErr,
    "str that changes between reads": _hostile_errors.Flip,
    "arg whose str changes between reads": lambda: TypeError(_hostile_errors.FlipArg()),
    "str arg whose str changes between reads": lambda: TypeError(_hostile_errors.FlipStr("x")),
    "second arg whose repr changes between reads": lambda: TypeError(
        "s", _hostile_errors.FlipRepr()
    ),
    "arg whose str lies about its length": lambda: TypeError(_hostile_errors.LyingText()),
    "notes set to a str": lambda: _hostile_errors.with_notes(HUGE),
    "notes set to a tuple": lambda: _hostile_errors.with_notes((HUGE,) * 3),
    "notes set to a dict": lambda: _hostile_errors.with_notes({"k": HUGE}),
    "notes set to a list subclass": lambda: _hostile_errors.with_notes(
        _hostile_errors.NoteList([HUGE])
    ),
    "a note that lies about its length": lambda: _hostile_errors.with_notes(
        [_hostile_errors.LyingStr(HUGE)]
    ),
    "raised from a huge error": lambda: _hostile_errors.chained_to(ValueError(HUGE)),
    "raised while handling a huge error": lambda: _hostile_errors.in_context_of(KeyError(HUGE)),
    "raised while handling a huge interrupt": lambda: _hostile_errors.in_context_of(
        KeyboardInterrupt(HUGE)
    ),
}


def _printed(error: BaseException) -> str:
    return "".join(traceback.format_exception(type(error), error, error.__traceback__))


def _before_the_start(error: Exception) -> tuple[object, ...]:
    return (_wire_targets.RaisesOnReduce(error),)


def _in_the_start(error: Exception) -> tuple[object, ...]:
    # The rehearsal pickles it once; the start's own pickling raises.
    return (multiprocessing.Lock(), _wire_targets.OnceThen(error))


@needs_pickling
@pytest.mark.parametrize("where", [_before_the_start, _in_the_start], ids=["before", "in start"])
@pytest.mark.parametrize("make", list(HOSTILE.values()), ids=list(HOSTILE))
def test_the_printed_error_of_a_call_that_cannot_be_sent_stays_short(
    make: Callable[[], Exception], where: Callable[[Exception], tuple[object, ...]]
) -> None:
    with pytest.raises(pickle.PicklingError, match=SENT) as info:
        run(_wire_targets.count, 30.0, args=where(make()), mode="process")
    cause = info.value.__cause__
    assert cause is not None
    assert info.value.__context__ in (None, cause)
    assert cause.__cause__ is None and cause.__context__ is None  # nothing chained to it
    printed = _printed(info.value)
    assert len(printed) < 10_000, len(printed)
    assert all(letter * 301 not in printed for letter in "HQYFABCD")


@needs_pickling
@pytest.mark.skipif(sys.version_info < (3, 11), reason="notes exist from Python 3.11")
def test_the_stand_in_keeps_the_notes_pickle_added_bounded() -> None:
    bad = _wire_targets.RaisesOnReduce(_hostile_errors.ReadOnlyArgs())
    try:
        pickle.dumps([{"k": bad}])
    except Exception as error:
        if not getattr(error, "__notes__", None):
            pytest.skip("this Python adds no notes to pickling errors")
    with pytest.raises(pickle.PicklingError, match=SENT) as info:
        run(_targets.echo, 30.0, args=([{"k" * 100: bad}],), mode="process")
    cause = info.value.__cause__
    assert type(cause) is RuntimeError
    notes = getattr(cause, "__notes__", None)
    assert notes, "the stand-in lost pickle's notes"
    assert any("item" in note for note in notes), notes
    assert all(len(note) <= 63 for note in notes), notes
