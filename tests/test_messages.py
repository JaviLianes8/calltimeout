"""Messages stay bounded and name calls without quoting what they were given."""

from __future__ import annotations

import functools
import pickle

import _targets
import _wire_targets
import pytest

from calltimeout import run, with_timeout

NAMES = "expected one of 'thread', 'process', 'signal'"


def test_a_quoted_value_of_exactly_60_characters_is_kept_whole() -> None:
    mode = "m" * 58  # its repr, quotes included, is 60 characters
    with pytest.raises(ValueError) as info:
        run(_targets.echo, 1.0, args=("",), mode=mode)  # type: ignore[call-overload]
    assert str(info.value) == f"unknown mode '{mode}': {NAMES}"


def test_a_quoted_value_of_61_characters_is_cut_after_60() -> None:
    mode = "m" * 59
    with pytest.raises(ValueError) as info:
        run(_targets.echo, 1.0, args=("",), mode=mode)  # type: ignore[call-overload]
    assert str(info.value) == f"unknown mode '{mode}...: {NAMES}"


def test_an_unpicklable_result_with_a_huge_error_gets_a_bounded_message() -> None:
    with pytest.raises(pickle.PicklingError) as info:
        run(_wire_targets.unpicklable_with_text, 30.0, args=(100_000,), mode="process")
    assert "cannot be sent back" in str(info.value)
    assert len(str(info.value)) <= 400


def test_an_unrebuildable_result_with_a_huge_error_gets_a_bounded_message() -> None:
    with pytest.raises(pickle.UnpicklingError) as info:
        run(_wire_targets.unrebuildable_with_text, 30.0, args=(100_000,), mode="process")
    assert "cannot be rebuilt" in str(info.value)
    assert len(str(info.value)) <= 400


def test_a_partial_is_named_by_its_type_never_by_its_bound_arguments() -> None:
    async def login(password: str) -> str:
        return password

    with pytest.raises(TypeError) as info:
        _ = run(functools.partial(login, "SENTINEL-secret"), 1.0)
    assert "SENTINEL" not in str(info.value)
    assert str(info.value).startswith("partial is a coroutine function")
    named = functools.partial(_wire_targets.thread_name)
    assert run(named, 5.0) == "calltimeout:partial"


def test_a_callable_whose_getattr_raises_something_else_still_runs() -> None:
    strict = _wire_targets.Strict()
    assert run(strict, 5.0) == "ran"
    assert run(strict, 5.0) == strict()
    assert with_timeout(5.0)(strict)() == "ran"
