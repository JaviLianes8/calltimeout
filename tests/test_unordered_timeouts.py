"""A real number that cannot be compared is still judged by its float value."""

from __future__ import annotations

import pytest

from calltimeout import CallTimeout, Mode, run, with_timeout


class Unordered(float):
    """A float whose own comparisons raise, so only its float value can be read."""

    def __lt__(self, other: object) -> bool:
        raise ArithmeticError("no order")

    def __le__(self, other: object) -> bool:
        raise ArithmeticError("no order")


# The smallest negative float, a fraction and a whole second: every one is below zero.
NEGATIVE = [-5e-324, -1e-9, -0.5, -1.0]


@pytest.mark.parametrize("value", NEGATIVE)
@pytest.mark.parametrize("mode", ["thread", "process"])
def test_run_refuses_an_unordered_negative_timeout(value: float, mode: Mode) -> None:
    calls: list[int] = []
    with pytest.raises(ValueError, match=r"^timeout must not be negative$"):
        run(calls.append, Unordered(value), args=(1,), mode=mode)
    assert calls == []


@pytest.mark.parametrize("value", NEGATIVE)
@pytest.mark.parametrize("mode", ["thread", "process"])
def test_with_timeout_refuses_an_unordered_negative_timeout(value: float, mode: Mode) -> None:
    with pytest.raises(ValueError, match=r"^timeout must not be negative$"):
        with_timeout(Unordered(value), mode=mode)


@pytest.mark.parametrize("value", [0.5, 2.0])
def test_an_unordered_positive_timeout_is_used(value: float) -> None:
    assert run(pow, Unordered(value), args=(2, 3)) == 8
    assert with_timeout(Unordered(value))(pow)(2, 3) == 8


@pytest.mark.parametrize("value", [0.0, -0.0])
def test_an_unordered_zero_timeout_is_a_zero_budget(value: float) -> None:
    calls: list[int] = []
    with pytest.raises(CallTimeout, match=r"within 0.0 seconds"):
        run(calls.append, Unordered(value), args=(1,))
    assert calls == []
