"""Process mode against a second implementation: pebble, run live on the same calls.

pebble (https://pypi.org/project/pebble/) runs a call in a fresh worker process with a
timeout and reports results, exceptions, crashes with their exit code and timeouts. On
seeded calls both must agree. Skips when pebble is not installed.
"""

from __future__ import annotations

import concurrent.futures
import os
import random
import time
from collections.abc import Callable, Iterator

import pytest

from calltimeout import CallCrashed, CallTimeout, run

pebble = pytest.importorskip("pebble")

SEED = 20261022


@pytest.fixture(scope="module")
def pool() -> Iterator[object]:
    # One task per worker, so every call starts in a fresh process as in process mode.
    with pebble.ProcessPool(max_workers=1, max_tasks=1) as workers:
        yield workers


def _outcome(call: Callable[[], object]) -> tuple[str, object]:
    try:
        return ("value", call())
    except (CallTimeout, TimeoutError, concurrent.futures.TimeoutError):
        # Python 3.10 still has a separate futures TimeoutError, which pebble raises there.
        return ("timeout", None)
    except CallCrashed as exc:
        return ("crash", exc.exitcode)
    except pebble.ProcessExpired as exc:
        return ("crash", exc.exitcode)
    except Exception as exc:
        return ("error", (type(exc), exc.args))


# pebble's answer when its own pool broke (seen under load, also with no calltimeout call
# running): no verdict on the call, so it is asked again in a fresh pool.
POOL_ERROR = ("error", (RuntimeError, ("Unexpected error within the Pool",)))


def _pebble(
    pool: object, fn: Callable[..., object], args: tuple[object, ...], budget: float
) -> object:
    theirs = _outcome(lambda: pool.schedule(fn, args=args, timeout=budget).result())  # type: ignore[attr-defined]
    for _ in range(3):
        if theirs != POOL_ERROR:
            break
        with pebble.ProcessPool(max_workers=1, max_tasks=1) as fresh:
            theirs = _outcome(lambda: fresh.schedule(fn, args=args, timeout=budget).result())
    return theirs


def _both(pool: object, fn: Callable[..., object], args: tuple[object, ...], budget: float) -> None:
    ours = _outcome(lambda: run(fn, budget, args=args, mode="process"))
    assert ours == _pebble(pool, fn, args, budget), (fn, args)


def _cases(rng: random.Random) -> Iterator[tuple[Callable[..., object], tuple[object, ...]]]:
    for _ in range(4):
        yield pow, (rng.randint(-50, 50), rng.randint(0, 40), rng.choice([7, 97, 10**9 + 7]))
    for _ in range(4):
        yield divmod, (rng.randint(-1000, 1000), rng.choice([0, rng.randint(1, 9)]))
    for _ in range(3):
        text = "".join(rng.choice("0123456789x -") for _ in range(rng.randint(0, 6)))
        yield int, (text,)
    yield sorted, ([rng.random() for _ in range(50)],)


def test_results_and_exceptions_agree(pool: object) -> None:
    for fn, args in _cases(random.Random(SEED)):
        _both(pool, fn, args, 30.0)


def test_crash_exit_codes_agree(pool: object) -> None:
    rng = random.Random(SEED + 1)
    for code in [1, *rng.sample(range(2, 256), 3)]:
        _both(pool, os._exit, (code,), 30.0)


def test_an_exit_with_code_zero_is_a_crash_here_and_a_timeout_in_a_pebble_pool(
    pool: object,
) -> None:
    # The one difference found: a pool worker that exits with 0 in the middle of a task
    # looks like a normal worker exit to pebble, so the task waits out its timeout.
    started = time.monotonic()
    assert _outcome(lambda: run(os._exit, 3.0, args=(0,), mode="process")) == ("crash", 0)
    assert time.monotonic() - started < 3.0
    assert _pebble(pool, os._exit, (0,), 3.0) == ("timeout", None)


def test_a_runaway_call_times_out_in_both(pool: object) -> None:
    started = time.monotonic()
    _both(pool, time.sleep, (60,), 0.5)
    assert time.monotonic() - started < 30
