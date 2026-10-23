"""Process mode: the error chained to a call that cannot be sent is short, whatever raised it."""

from __future__ import annotations

import multiprocessing
import pickle
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

HOSTILE: dict[str, Callable[[], Exception]] = {
    "args that cannot be set": _hostile_errors.ReadOnlyArgs,
    "text from __str__": _hostile_errors.LongText,
    "two args": lambda: TypeError("y" * 5000, 2),
    "one long arg": lambda: TypeError("x" * 5000),
}


@needs_pickling
@pytest.mark.parametrize("make", list(HOSTILE.values()), ids=list(HOSTILE))
def test_the_chained_error_is_cut_after_300_characters_whatever_raised_it(
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


@needs_pickling
def test_an_error_whose_str_raises_still_gives_pickling_error() -> None:
    bad = _wire_targets.RaisesOnReduce(_hostile_errors.BadStr("refused"))
    with pytest.raises(pickle.PicklingError, match=SENT) as info:
        run(_targets.echo, 30.0, args=(bad,), mode="process")
    assert "BadStr('refused')" in str(info.value)


@needs_pickling
def test_exactly_300_characters_of_the_chained_error_are_kept() -> None:
    token = _wire_targets.SecretToken("TOPSECRET-" + "s" * 100_000)
    with pytest.raises(pickle.PicklingError, match=SENT) as info:
        run(_targets.echo, 30.0, args=(token,), mode="process")
    cause = str(info.value.__cause__)
    assert len(cause) == 303, cause
    assert cause.endswith("...")
    assert not cause[:300].endswith("...")


def test_exactly_300_characters_of_a_results_pickling_error_are_kept() -> None:
    with pytest.raises(pickle.PicklingError) as info:
        run(_wire_targets.unpicklable_with_text, 30.0, args=(1000,), mode="process")
    prefix = "the call's result cannot be sent back: "
    message = str(info.value)
    assert message.startswith(prefix)
    assert len(message) == len(prefix) + 303, message
    assert message.endswith("x...")
