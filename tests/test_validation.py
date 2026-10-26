"""Arguments are checked before anything starts, the same way in every mode."""

from __future__ import annotations

import math
import sys
import threading
from collections.abc import Callable
from fractions import Fraction

import _targets
import pytest

from calltimeout import CallTimeout, Mode, run, with_timeout

MODES: list[Mode] = ["thread", "process"]
if sys.platform != "win32":
    MODES.append("signal")


async def _coroutine_function() -> int:
    return 1


def _returns_coroutine() -> object:
    return _coroutine_function()


@pytest.mark.parametrize("timeout", [True, "1", None, b"1", 1j])
def test_rejects_a_timeout_that_is_not_a_number(timeout: object) -> None:
    with pytest.raises(TypeError, match="timeout must be a number"):
        run(_targets.echo, timeout, args=(1,))  # type: ignore[call-overload]


@pytest.mark.parametrize(
    ("timeout", "message"),
    [
        (-1.0, "negative"),
        (-1e-9, "negative"),
        (math.nan, "NaN"),
        (math.inf, "at most"),
        (threading.TIMEOUT_MAX * 2, "at most"),
    ],
)
def test_rejects_an_unusable_timeout(timeout: float, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        run(_targets.echo, timeout, args=(1,))


@pytest.mark.parametrize("timeout", [-(10**400), Fraction(-(10**400), 3)], ids=["int", "fraction"])
def test_a_negative_timeout_too_large_for_a_float_is_called_negative(timeout: object) -> None:
    with pytest.raises(ValueError, match="must not be negative"):
        run(_targets.echo, timeout, args=(1,))  # type: ignore[call-overload]


@pytest.mark.parametrize("timeout", [10**400, Fraction(10**400, 3)], ids=["int", "fraction"])
def test_a_positive_timeout_too_large_for_a_float_is_above_the_limit(timeout: object) -> None:
    with pytest.raises(ValueError, match="at most"):
        run(_targets.echo, timeout, args=(1,))  # type: ignore[call-overload]


def test_accepts_an_integer_timeout() -> None:
    assert run(_targets.echo, 1, args=("int",)) == "int"


@pytest.mark.parametrize("mode", MODES)
def test_a_zero_budget_raises_without_starting_the_call(mode: Mode) -> None:
    started: list[int] = []
    with pytest.raises(CallTimeout) as info:
        run(started.append, 0, args=(1,), mode=mode)
    assert started == []
    assert info.value.timeout == 0


def test_a_zero_budget_returns_the_default() -> None:
    assert run(_targets.echo, 0.0, args=(1,), default="none") == "none"


def test_rejects_an_unknown_mode() -> None:
    with pytest.raises(ValueError, match="unknown mode"):
        run(_targets.echo, 1.0, args=("x",), mode="bogus")  # type: ignore[call-overload]


def test_rejects_something_that_is_not_callable() -> None:
    with pytest.raises(TypeError, match="callable"):
        run(42, 1.0)  # type: ignore[call-overload]


def test_rejects_args_that_are_not_a_tuple() -> None:
    with pytest.raises(TypeError, match="args must be a tuple"):
        run(_targets.echo, 1.0, args=[1])  # type: ignore[call-overload]


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("kwargs", [[], 0, "", (), b""])
def test_rejects_kwargs_that_are_falsy_but_not_a_mapping(kwargs: object, mode: Mode) -> None:
    started: list[int] = []
    with pytest.raises(TypeError, match="kwargs must be a mapping, not"):
        run(started.append, 5.0, args=(1,), kwargs=kwargs, mode=mode)  # type: ignore[call-overload]
    assert started == []


def test_rejects_kwargs_with_keys_that_are_not_strings() -> None:
    with pytest.raises(TypeError, match="keys must be strings"):
        run(_targets.echo, 1.0, kwargs={1: 2})  # type: ignore[dict-item]


@pytest.mark.parametrize("mode", MODES)
def test_rejects_a_coroutine_function(mode: Mode) -> None:
    with pytest.raises(TypeError, match=r"asyncio\.timeout"):
        _ = run(_coroutine_function, 30.0, mode=mode)


@pytest.mark.filterwarnings("error")
@pytest.mark.parametrize("mode", MODES)
def test_rejects_a_coroutine_returned_by_the_call(mode: Mode) -> None:
    with pytest.raises(TypeError, match="returned a coroutine"):
        run(_returns_coroutine, 30.0, mode=mode)


@pytest.mark.parametrize(
    "decorate",
    [
        lambda: with_timeout(-1.0),
        lambda: with_timeout(math.nan),
        lambda: with_timeout(1.0, mode="bogus"),  # type: ignore[call-overload]
    ],
)
def test_the_decorator_rejects_bad_settings_when_applied(decorate: Callable[[], object]) -> None:
    with pytest.raises(ValueError):
        decorate()


def test_the_decorator_rejects_a_coroutine_function() -> None:
    with pytest.raises(TypeError, match=r"asyncio\.timeout"):
        with_timeout(1.0)(_coroutine_function)
