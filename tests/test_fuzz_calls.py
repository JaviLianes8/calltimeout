"""Seeded calls through every mode give exactly what calling the function directly gives.

The oracle is the plain call ``fn(*args, **kwargs)`` in this thread: the same value, or an
exception of the same type with the same arguments. The calls are builtins with random,
often invalid, arguments, so both outcomes are exercised.
"""

from __future__ import annotations

import pickle
import random
import sys
from collections.abc import Callable, Iterator
from typing import Any

import pytest

from calltimeout import CallCrashed, CallTimeout, Mode, run

Call = tuple[Callable[..., object], tuple[object, ...], dict[str, Any]]


def _text(rng: random.Random, alphabet: str, longest: int) -> str:
    return "".join(rng.choice(alphabet) for _ in range(rng.randint(0, longest)))


def _calls(rng: random.Random, count: int) -> Iterator[Call]:
    for _ in range(count):
        kind = rng.randrange(9)
        if kind == 0:
            mod = rng.choice([None, 0, 1, 7, -5, 10**9 + 7])
            yield pow, (rng.randint(-99, 99), rng.randint(-3, 60), mod), {}
        elif kind == 1:
            yield divmod, (rng.uniform(-1e6, 1e6), rng.choice([0, 0.0, 3, -2.5])), {}
        elif kind == 2:
            yield (
                int,
                (_text(rng, "0123456789abcxz_ -+", 8),),
                {"base": rng.choice([0, 2, 10, 16, 36, 37])},
            )
        elif kind == 3:
            values = [rng.choice([rng.random(), rng.randint(-9, 9), "s", None]) for _ in range(6)]
            yield sorted, (values,), {"reverse": rng.random() < 0.5}
        elif kind == 4:
            yield bytes.fromhex, (_text(rng, "0123456789abcdefg ", 10),), {}
        elif kind == 5:
            yield round, (rng.uniform(-1e3, 1e3), rng.randint(-3, 5)), {}
        elif kind == 6:
            yield max, ([rng.randint(0, 9) for _ in range(rng.randint(0, 3))],), {}
        elif kind == 7:
            yield str.split, (_text(rng, "ab, ", 12), rng.choice([",", " ", "", None])), {}
        else:
            yield float, (_text(rng, "0123456789.eE+-infa", 8),), {}


def _direct(fn: Callable[..., object], args: tuple[object, ...], kwargs: dict[str, Any]) -> object:
    try:
        return ("value", repr(fn(*args, **kwargs)))  # repr: NaN is not equal to itself
    except Exception as exc:
        return ("error", type(exc), exc.args)


def _through(mode: Mode, call: Call) -> object:
    fn, args, kwargs = call
    return _direct(lambda: run(fn, 30.0, args=args, kwargs=kwargs, mode=mode), (), {})


def _check(mode: Mode, seed: int, count: int) -> None:
    for call in _calls(random.Random(seed), count):
        assert _through(mode, call) == _direct(*call), call


@pytest.mark.parametrize("seed", [7, 2026, 31337])
def test_thread_mode_agrees_with_the_direct_call(seed: int) -> None:
    _check("thread", seed, 1500)


@pytest.mark.skipif(sys.platform == "win32", reason="signal mode is POSIX")
@pytest.mark.parametrize("seed", [7, 2026])
def test_signal_mode_agrees_with_the_direct_call(seed: int) -> None:
    _check("signal", seed, 1500)


def test_process_mode_agrees_with_the_direct_call() -> None:
    _check("process", 4242, 40)


@pytest.mark.parametrize("seed", [3, 4])
def test_the_exceptions_round_trip_with_any_number(seed: int) -> None:
    rng = random.Random(seed)
    for _ in range(3000):
        timeout = rng.choice([rng.random() * 10 ** rng.randint(-9, 9), rng.randint(0, 10**30)])
        code = rng.choice([rng.randint(-64, 255), rng.randint(-(2**70), 2**70)])
        for error in (CallTimeout(timeout), CallCrashed(code)):
            clone = pickle.loads(pickle.dumps(error))
            assert (type(clone), str(clone), vars(clone)) == (type(error), str(error), vars(error))
            assert len(str(error)) <= 120
