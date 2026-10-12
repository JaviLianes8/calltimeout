"""Argument checks shared by every mode."""

from __future__ import annotations

import inspect
import math
import threading
from collections.abc import Iterable, Mapping
from numbers import Real
from typing import TypeVar

T = TypeVar("T")

_ASYNC_HINT = "use asyncio.timeout() for coroutines; calltimeout runs blocking callables"


def check_timeout(timeout: object) -> float:
    """Return the budget as a float, or raise if it is not a usable number of seconds."""
    if isinstance(timeout, bool) or not isinstance(timeout, Real):
        raise TypeError(f"timeout must be a number of seconds, not {type(timeout).__name__}")
    try:
        seconds = float(timeout) + 0.0  # + 0.0 turns -0.0 into 0.0
    except OverflowError:
        raise ValueError(f"timeout must be at most {threading.TIMEOUT_MAX} seconds") from None
    if math.isnan(seconds):
        raise ValueError("timeout must be a number, not NaN")
    if seconds < 0:
        raise ValueError("timeout must not be negative")
    if seconds > threading.TIMEOUT_MAX:
        # Covers infinity too: every wait primitive rejects values above this limit.
        raise ValueError(f"timeout must be at most {threading.TIMEOUT_MAX} seconds")
    return seconds


def check_call(fn: object, args: object, kwargs: object) -> None:
    """Reject arguments the call could never run with, before anything is started."""
    if not callable(fn):
        raise TypeError(f"fn must be callable, not {type(fn).__name__}")
    if inspect.iscoroutinefunction(fn):
        raise TypeError(f"{fn!r} is a coroutine function: {_ASYNC_HINT}")
    if not isinstance(args, tuple):
        raise TypeError(f"args must be a tuple, not {type(args).__name__}")
    if kwargs is not None and not isinstance(kwargs, Mapping):
        raise TypeError(f"kwargs must be a mapping, not {type(kwargs).__name__}")
    if kwargs is not None and not all(isinstance(key, str) for key in kwargs):
        raise TypeError("kwargs keys must be strings")


def check_mode(mode: object, modes: Iterable[str]) -> None:
    """Reject anything but one of the mode names, including unhashable values."""
    if not isinstance(mode, str) or mode not in modes:
        raise ValueError(f"unknown mode: {mode!r}")


def reject_coroutine(value: T) -> T:
    """Refuse a coroutine result: it would never run and warn later as unawaited."""
    if inspect.iscoroutine(value):
        value.close()
        raise TypeError(f"the call returned a coroutine: {_ASYNC_HINT}")
    return value
