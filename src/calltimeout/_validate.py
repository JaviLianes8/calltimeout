"""Argument checks shared by every mode."""

from __future__ import annotations

import inspect
import math
import threading
from collections.abc import Iterable, Mapping
from numbers import Real
from typing import TypeVar

from ._text import call_name, shown, type_name

T = TypeVar("T")

# asyncio.timeout() is new in Python 3.11; asyncio.wait_for() exists on every supported one.
_ASYNC_HINT = (
    "use asyncio.timeout() (Python 3.11+) or asyncio.wait_for() for coroutines;"
    " calltimeout runs blocking callables"
)


def check_timeout(timeout: object) -> float:
    """Return the budget as a float, or raise if it is not a usable number of seconds."""
    if isinstance(timeout, bool) or not isinstance(timeout, Real):
        raise TypeError(f"timeout must be a number of seconds, not {type_name(timeout)}")
    try:
        seconds = float(timeout) + 0.0  # + 0.0 turns -0.0 into 0.0
    except OverflowError:
        raise ValueError(f"timeout must be at most {threading.TIMEOUT_MAX} seconds") from None
    except Exception as exc:
        # A Real whose own conversion fails: still a bad argument, reported as one.
        raise TypeError(f"timeout {type_name(timeout)} cannot be read as seconds") from exc
    if math.isnan(seconds):
        raise ValueError("timeout must be a number, not NaN")
    if seconds < 0:
        raise ValueError("timeout must not be negative")
    if seconds > threading.TIMEOUT_MAX:
        # Covers infinity too: every wait primitive rejects values above this limit.
        raise ValueError(f"timeout must be at most {threading.TIMEOUT_MAX} seconds")
    return seconds


def _is_coroutine_function(fn: object) -> bool:
    try:
        return inspect.iscoroutinefunction(fn)
    except Exception:
        # Its own __getattr__ raised while inspect looked around: the call itself may
        # still work, and the object's error is no argument error of ours.
        return False


def check_call(fn: object, args: object, kwargs: object) -> dict[str, object]:
    """Reject arguments the call could never run with; return kwargs as the call gets them."""
    if not callable(fn):
        raise TypeError(f"fn must be callable, not {type_name(fn)}")
    if _is_coroutine_function(fn):
        # Named, not repr'd: the repr of a partial would quote its bound arguments.
        raise TypeError(f"{call_name(fn)} is a coroutine function: {_ASYNC_HINT}")
    if not isinstance(args, tuple):
        raise TypeError(f"args must be a tuple, not {type_name(args)}")
    if kwargs is None:
        return {}
    if not isinstance(kwargs, Mapping):
        raise TypeError(f"kwargs must be a mapping, not {type_name(kwargs)}")
    # Read once and checked as read: a mapping whose views disagree, or change between
    # reads, cannot pass the check with one set of keys and call with another.
    copy = dict(kwargs)
    if not all(isinstance(key, str) for key in copy):
        raise TypeError("kwargs keys must be strings")
    return copy


def check_mode(mode: object, modes: Iterable[str]) -> str:
    """Return the mode as a plain str, or raise TypeError or ValueError."""
    if not isinstance(mode, str):
        raise TypeError(f"mode must be a str, not {type_name(mode)}")
    # A str subclass cannot change how the name compares or hashes from here on.
    name = str.__str__(mode)
    names = list(modes)
    if name not in names:
        expected = ", ".join(repr(each) for each in names)
        raise ValueError(f"unknown mode {shown(name)}: expected one of {expected}")
    return name


def reject_coroutine(value: T) -> T:
    """Refuse a coroutine result: it would never run and warn later as unawaited."""
    if inspect.iscoroutine(value):
        value.close()
        raise TypeError(f"the call returned a coroutine: {_ASYNC_HINT}")
    return value
