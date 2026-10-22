"""Seeded fuzz of the argument checks against the documented rules, with hostile values.

The rules (README, GUIDE, ``run`` docstring): a timeout is a real number that is not a
bool, converts to a float that is not NaN, not negative and at most threading.TIMEOUT_MAX;
a mode is one of three str names. Anything else is a TypeError or ValueError raised before
the call starts, with a short message.
"""

from __future__ import annotations

import decimal
import fractions
import math
import random
import sys
import threading
import time
from collections.abc import Iterator
from numbers import Real

import _targets
import pytest

from calltimeout import CallTimeout, run

SEEDS = [1, 2026, 99991]
LONGEST = 300  # characters any argument error message may take


def _timeouts(rng: random.Random) -> Iterator[object]:
    edges: list[object] = [0, -0.0, 0.0, 1, True, False, None, "1", b"1", 1j, math.nan]
    edges += [math.inf, -math.inf, threading.TIMEOUT_MAX, threading.TIMEOUT_MAX * 1.0000001]
    edges += [5e-324, -5e-324, 10**400, -(10**400), decimal.Decimal("1"), fractions.Fraction(1, 3)]
    yield from edges
    for _ in range(1500):
        kind = rng.randrange(6)
        if kind == 0:
            yield rng.uniform(-1e3, 1e3)
        elif kind == 1:
            yield rng.choice([-1, 1]) * 10 ** rng.randint(0, 600)
        elif kind == 2:
            yield fractions.Fraction(rng.randint(-50, 50), rng.randint(1, 50))
        elif kind == 3:
            yield math.ldexp(rng.random(), rng.randint(-1100, 1020))
        elif kind == 4:
            yield "".join(rng.choice("0123456789.-e") for _ in range(rng.randint(0, 8)))
        else:
            yield rng.choice([[], (), {}, object(), b"", bytearray(3), range(2)])


def _expected(value: object) -> type[BaseException] | None:
    # Written from the documented rules, not from the code.
    if isinstance(value, bool) or not isinstance(value, Real):
        return TypeError
    try:
        seconds = float(value)
    except OverflowError:
        return ValueError
    if math.isnan(seconds) or seconds < 0 or seconds > threading.TIMEOUT_MAX:
        return ValueError
    return None


@pytest.mark.parametrize("seed", SEEDS)
def test_every_timeout_is_judged_by_the_documented_rules(seed: int) -> None:
    for value in _timeouts(random.Random(seed)):
        expected = _expected(value)
        if expected is None:
            if float(value) == 0:  # type: ignore[arg-type]
                with pytest.raises(CallTimeout):
                    run(_targets.echo, value, args=(1,))  # type: ignore[call-overload]
            else:
                assert run(_targets.echo, value, args=(1,)) == 1  # type: ignore[call-overload]
            continue
        with pytest.raises(expected) as info:
            run(_targets.echo, value, args=(1,))  # type: ignore[call-overload]
        assert len(str(info.value)) <= LONGEST, repr(value)[:80]


def _modes(rng: random.Random) -> Iterator[object]:
    yield from ["thread", "process", "signal", "Thread", "thread ", "", "fiber", "\x00"]
    yield from [None, 1, b"thread", ["thread"], ("thread",), {"thread": 1}]
    alphabet = "threadpocsignal _-é中\U0001f600\x00"
    for _ in range(1000):
        yield "".join(rng.choice(alphabet) for _ in range(rng.randint(0, 12)))
    yield "x" * 1_000_000


@pytest.mark.parametrize("seed", SEEDS)
def test_only_the_three_mode_names_are_accepted(seed: int) -> None:
    for mode in _modes(random.Random(seed)):
        if mode in ("thread", "process") and isinstance(mode, str):
            with pytest.raises(CallTimeout):
                run(_targets.echo, 0, args=(1,), mode=mode)
            continue
        if mode == "signal":
            continue  # platform rules: tested in test_signal_*
        expected = TypeError if not isinstance(mode, str) else ValueError
        with pytest.raises(expected) as info:
            run(_targets.echo, 0, args=(1,), mode=mode)  # type: ignore[call-overload]
        assert len(str(info.value)) <= LONGEST


class _Hostile:
    """Every way of describing itself fails."""

    def __repr__(self) -> str:
        raise RuntimeError("repr")

    def __str__(self) -> str:
        raise RuntimeError("str")


class _FailingReal(float):
    def __float__(self) -> float:
        raise RuntimeError("no float")


def test_hostile_arguments_still_get_a_short_typed_error() -> None:
    cases: list[tuple[dict[str, object], type[BaseException]]] = [
        ({"fn": _Hostile()}, TypeError),
        ({"timeout": _Hostile()}, TypeError),
        ({"timeout": _FailingReal(1.0)}, TypeError),
        ({"args": _Hostile()}, TypeError),
        ({"kwargs": _Hostile()}, TypeError),
        ({"mode": _Hostile()}, TypeError),
        ({"mode": type("M" * 100_000, (str,), {})("bogus")}, ValueError),
        ({"timeout": type("T" * 100_000, (), {})()}, TypeError),
    ]
    for override, expected in cases:
        call: dict[str, object] = {"fn": _targets.echo, "timeout": 1.0, "args": (1,)}
        call.update(override)
        fn, timeout = call.pop("fn"), call.pop("timeout")
        with pytest.raises(expected) as info:
            run(fn, timeout, **call)  # type: ignore[call-overload]
        assert len(str(info.value)) <= LONGEST, override


@pytest.mark.parametrize("size", [25_000, 100_000])
def test_many_keyword_arguments_are_checked_in_linear_time(size: int) -> None:
    kwargs = {f"k{i}": i for i in range(size)}
    started = time.perf_counter()
    assert run(lambda **seen: len(seen), 30.0, kwargs=kwargs) == size
    assert time.perf_counter() - started < 10.0 * size / 25_000


def test_a_long_coroutine_name_is_cut_in_the_message() -> None:
    async def job() -> None:
        return None

    job.__qualname__ = "j" * 100_000
    with pytest.raises(TypeError) as info:
        _ = run(job, 1.0)
    assert len(str(info.value)) <= LONGEST
    assert sys.getsizeof(str(info.value)) < 2_000
