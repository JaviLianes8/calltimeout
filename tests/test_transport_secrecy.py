"""Transport diagnostics omit caller text in every direction across the process boundary."""

from __future__ import annotations

import multiprocessing
import pickle
import traceback
from typing import NoReturn

import pytest

from calltimeout import run

SECRET = "TOKEN_PRIVATE_7fb52e36"


def refuse() -> NoReturn:
    error = ValueError(SECRET + "x" * 100_000)
    vars(error)["__notes__"] = [SECRET]
    raise error from LookupError(SECRET)


class BadReduce:
    def __reduce__(self) -> tuple[object, ...]:
        return refuse()


class BadRebuild:
    def __reduce__(self) -> tuple[object, ...]:
        return (refuse, ())


def echo(value: object) -> object:
    return value


def result(rebuild: bool) -> object:
    return BadRebuild() if rebuild else BadReduce()


@pytest.mark.parametrize("direction", ["send", "load", "send back", "rebuild"])
def test_transport_errors_omit_values_notes_and_original_chains(direction: str) -> None:
    if direction in ("send", "load") and multiprocessing.get_start_method() == "fork":
        pytest.skip("fork does not pickle the call")
    kind = pickle.PicklingError if direction in ("send", "send back") else pickle.UnpicklingError
    with pytest.raises(kind) as info:
        if direction in ("send", "load"):
            value = BadReduce() if direction == "send" else BadRebuild()
            run(echo, 10, args=(value,), mode="process")
        else:
            run(result, 10, args=(direction == "rebuild",), mode="process")
    pending: list[BaseException] = [info.value]
    seen: set[int] = set()
    while pending:
        error = pending.pop()
        if id(error) in seen:
            continue
        seen.add(id(error))
        text = "".join(traceback.format_exception(type(error), error, error.__traceback__))
        assert SECRET not in text
        assert len(text) < 10_000
        pending.extend(e for e in (error.__cause__, error.__context__) if e is not None)
