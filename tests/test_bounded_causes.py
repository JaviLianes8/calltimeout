"""Process mode: the error chained to a call that cannot be sent is short, whatever raised it."""

from __future__ import annotations

import multiprocessing
import pickle
from collections.abc import Callable

import _hostile_errors
import _targets
import _wire_targets
import pytest

from calltimeout import _causes, run

needs_pickling = pytest.mark.skipif(
    multiprocessing.get_start_method() == "fork", reason="fork pickles nothing"
)

SENT = "the call cannot be sent to the child process"

HOSTILE: dict[str, Callable[[], Exception]] = {
    "args that cannot be set": _hostile_errors.ReadOnlyArgs,
    "text from __str__": _hostile_errors.LongText,
    "two args": lambda: TypeError("y" * 5000, 2),
    "one long arg": lambda: TypeError("x" * 5000),
}


@needs_pickling
@pytest.mark.parametrize("make", list(HOSTILE.values()), ids=list(HOSTILE))
def test_the_chained_error_is_value_free_whatever_raised_it(
    make: Callable[[], Exception],
) -> None:
    bad = _wire_targets.RaisesOnReduce(make())
    with pytest.raises(pickle.PicklingError, match=SENT) as info:
        run(_targets.echo, 30.0, args=(bad,), mode="process")
    assert info.value.__context__ in (None, info.value.__cause__)  # nothing unbounded kept
    cause = str(info.value.__cause__)
    assert len(cause) <= 303, len(cause)
    assert "L" * 301 not in cause
    assert len(str(info.value)) <= len(SENT) + 2 + 63


STAND_IN: dict[str, type[Exception]] = {
    "args that cannot be set": _hostile_errors.ReadOnlyArgs,
    "text from __str__": _hostile_errors.LongText,
}


@needs_pickling
@pytest.mark.parametrize("kind", list(STAND_IN.values()), ids=list(STAND_IN))
def test_a_custom_error_is_replaced_without_naming_or_reading_it(
    kind: type[Exception],
) -> None:
    bad = _wire_targets.RaisesOnReduce(kind())
    with pytest.raises(pickle.PicklingError, match=SENT) as info:
        run(_targets.echo, 30.0, args=(bad,), mode="process")
    cause = info.value.__cause__
    assert type(cause) is RuntimeError
    assert str(cause) == "transport operation failed"


@needs_pickling
@pytest.mark.parametrize("size", [300, 301, 400, 599, 5000])
@pytest.mark.parametrize("args", [1, 2], ids=["one arg", "two args"])
def test_a_plain_error_is_replaced_without_mutating_its_arguments(size: int, args: int) -> None:
    error = TypeError("x" * size, *range(args - 1))
    bad = _wire_targets.RaisesOnReduce(error)
    with pytest.raises(pickle.PicklingError, match=SENT) as info:
        run(_targets.echo, 30.0, args=(bad,), mode="process")
    cause = info.value.__cause__
    assert type(cause) is TypeError  # its own type, kept
    assert str(cause) == "transport operation failed"
    assert cause is not error
    assert error.args == ("x" * size, *range(args - 1))


@needs_pickling
def test_an_error_whose_str_raises_still_gives_pickling_error() -> None:
    bad = _wire_targets.RaisesOnReduce(_hostile_errors.BadStr("refused"))
    with pytest.raises(pickle.PicklingError, match=SENT) as info:
        run(_targets.echo, 30.0, args=(bad,), mode="process")
    assert type(info.value.__cause__) is RuntimeError
    assert str(info.value) == f"{SENT}: RuntimeError"


@needs_pickling
def test_the_chained_error_omits_even_a_short_secret_prefix() -> None:
    token = _wire_targets.SecretToken("TOPSECRET-" + "s" * 100_000)
    with pytest.raises(pickle.PicklingError, match=SENT) as info:
        run(_targets.echo, 30.0, args=(token,), mode="process")
    cause = str(info.value.__cause__)
    assert cause == "transport operation failed"
    assert "TOPSECRET" not in str(info.value)


def test_a_results_pickling_error_reports_only_a_safe_category() -> None:
    with pytest.raises(pickle.PicklingError) as info:
        run(_wire_targets.unpicklable_with_text, 30.0, args=(1000,), mode="process")
    prefix = "the call's result cannot be sent back: "
    message = str(info.value)
    assert message == prefix + "ValueError"
    assert "ValueError: transport operation failed" in str(info.value.__cause__)
    assert "x" * 10 not in str(info.value.__cause__)


class _BigNote:
    def __str__(self) -> str:
        return "N" * 5000


@needs_pickling
def test_notes_are_discarded_without_calling_their_string_hooks() -> None:
    error = TypeError("cannot pickle this")
    vars(error)["__notes__"] = [_BigNote(), "kept"]  # set directly: Python 3.10 has no add_note
    with pytest.raises(pickle.PicklingError, match=SENT) as info:
        run(len, 30.0, args=(_wire_targets.RaisesOnReduce(error),), mode="process")
    assert "__notes__" not in vars(info.value.__cause__)


@pytest.mark.parametrize(
    "notes",
    ["N" * 1000, [_BigNote()], 7],
    ids=["one str", "not text", "not a list"],
)
def test_notes_are_discarded_whatever_they_were_set_to(notes: object) -> None:
    # Python 3.14's pickle replaces an error whose notes are a str (it cannot add its
    # own), so that shape is checked on the bounding itself.
    error = TypeError("cannot pickle this")
    vars(error)["__notes__"] = notes
    assert "__notes__" not in vars(_causes.bounded(error))
    assert vars(error)["__notes__"] is notes
