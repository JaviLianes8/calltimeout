"""Argument checks shared by every mode."""

from __future__ import annotations

import gc
import inspect
import math
import threading
from collections.abc import Iterable, Mapping
from numbers import Real
from types import GetSetDescriptorType, MappingProxyType
from typing import TypeVar, cast

from ._text import call_name, type_name

T = TypeVar("T")

# asyncio.timeout() is new in Python 3.11; asyncio.wait_for() exists on every supported one.
_ASYNC_HINT = (
    "use asyncio.timeout() (Python 3.11+) or asyncio.wait_for() for coroutines;"
    " calltimeout runs blocking callables"
)


def _actual_type(value: object, expected: type) -> bool:
    try:
        return issubclass(type(value), expected)
    except Exception:
        return False  # ABC registration may consult a custom metaclass.


def _is_negative(number: Real) -> bool:
    """Read the original sign before float conversion can overflow or underflow."""
    try:
        return bool(number < 0)
    except Exception:
        return False  # Float conversion still determines whether this number is usable.


def check_timeout(timeout: object) -> float:
    """Return the budget as a float, or raise if it is not a usable number of seconds."""
    if type(timeout) is bool or not _actual_type(timeout, Real):
        raise TypeError(f"timeout must be a number of seconds, not {type_name(timeout)}")
    number = cast(Real, timeout)
    if _is_negative(number):
        raise ValueError("timeout must not be negative")
    try:
        seconds = float(number) + 0.0  # + 0.0 turns -0.0 into 0.0
    except OverflowError:
        error: Exception = ValueError(f"timeout must be at most {threading.TIMEOUT_MAX} seconds")
    except Exception:
        error = TypeError("timeout cannot be read as seconds")
    else:
        return _check_seconds(seconds)
    # Outside the handler: even the suppressed context must not retain caller text.
    raise error


def _check_seconds(seconds: float) -> float:
    if math.isnan(seconds):
        raise ValueError("timeout must be a number, not NaN")
    if seconds < 0:
        raise ValueError("timeout must not be negative")
    if seconds > threading.TIMEOUT_MAX:
        # Covers infinity too: every wait primitive rejects values above this limit.
        raise ValueError(f"timeout must be at most {threading.TIMEOUT_MAX} seconds")
    return seconds


# A generator function returns at once: its body runs as it is iterated, after run returned.
_GENERATOR_HINT = (
    "its body runs only as the generator is iterated, after the call returned, outside the"
    " budget; run a function that consumes it instead"
)


def _deferred_kind(fn: object) -> str | None:
    """The kind of function whose body a call does not run, or None."""
    try:
        if inspect.iscoroutinefunction(fn):
            return f"a coroutine function: {_ASYNC_HINT}"
        if inspect.isasyncgenfunction(fn):
            return f"an async generator function: {_ASYNC_HINT}"
        if inspect.isgeneratorfunction(fn):
            return f"a generator function: {_GENERATOR_HINT}"
    except Exception:
        # Its own __getattr__ raised while inspect looked around: the call itself may
        # still work, and the object's error is no argument error of ours.
        pass
    return None


def check_call(fn: object, args: object, kwargs: object) -> dict[str, object]:
    """Reject arguments the call could never run with; return kwargs as the call gets them."""
    if not callable(fn):
        raise TypeError(f"fn must be callable, not {type_name(fn)}")
    kind = _deferred_kind(fn)
    if kind is not None:
        # Named, not repr'd: the repr of a partial would quote its bound arguments.
        raise TypeError(f"{call_name(fn)} is {kind}")
    if not _actual_type(args, tuple):
        raise TypeError(f"args must be a tuple, not {type_name(args)}")
    if kwargs is None:
        return {}
    if not _actual_type(kwargs, Mapping):
        raise TypeError(f"kwargs must be a mapping, not {type_name(kwargs)}")
    return _keywords(cast(Mapping[object, object], kwargs))


def _stored_keywords(value: object) -> dict[object, object] | None:
    # CPython exposes a proxy's backing mapping to GC traversal. If an interpreter
    # does not expose exactly one referent, keep the ordinary mapping read path.
    while type(value) is MappingProxyType:
        referents = gc.get_referents(value)
        if len(referents) != 1:
            return None
        value = referents[0]
    if type(value) is dict:
        return cast(dict[object, object], value)
    # Custom metaclasses can hide overridden methods from static lookup.
    if not _actual_type(value, dict) or type(type(value)) is not type:
        return None
    names = ("keys", "__getitem__", "__getattribute__")
    # Read the real namespace directly: static instance lookup misses aliased descriptors.
    for owner in type(value).__mro__:
        if "__dict__" in owner.__dict__:
            namespace = owner.__dict__["__dict__"]
            if (
                type(namespace) is not GetSetDescriptorType
                or namespace.__name__ != "__dict__"
                or namespace.__objclass__ not in type(value).__mro__
                or namespace.__objclass__.__dict__.get("__dict__") is not namespace
            ):
                return None
            attributes = cast(GetSetDescriptorType, namespace).__get__(value, type(value))
            if any(dict.__contains__(attributes, name) for name in names):
                return None
            break
    if all(
        inspect.getattr_static(type(value), name) is inspect.getattr_static(dict, name)
        for name in names
    ):
        return cast(dict[object, object], value)
    return None


def _keywords(kwargs: Mapping[object, object]) -> dict[str, object]:
    # Read once and checked as read: a mapping whose views disagree, or change between
    # reads, cannot pass the check with one set of keys and call with another.
    copy: dict[str, object] = {}
    try:
        # Bypass items overrides only when keys and lookup use dictionary semantics.
        # Other mappings defer value access until their keys have been validated.
        stored = _stored_keywords(kwargs)
        keys = kwargs.keys()
        pairs = dict.items(stored) if stored is not None else ((key, None) for key in keys)
        for key, value in pairs:
            if not _actual_type(key, str):
                break
            # Normalize before insertion: user hashes and equality can collide or raise.
            name = str.__str__(cast(str, key))
            copy[name] = value if stored is not None else kwargs[key]
        else:
            return copy
    except Exception:
        error = TypeError("kwargs mapping cannot be read")
    else:
        error = TypeError("kwargs keys must be strings")
    raise error


def check_mode(mode: object, modes: Iterable[str]) -> str:
    """Return the mode as a plain str, or raise TypeError or ValueError."""
    if not _actual_type(mode, str):
        raise TypeError(f"mode must be a str, not {type_name(mode)}")
    # A str subclass cannot change how the name compares or hashes from here on.
    name = str.__str__(cast(str, mode))
    names = list(modes)
    if name not in names:
        expected = ", ".join(repr(each) for each in names)
        raise ValueError(f"unknown mode: expected one of {expected}")
    return name


def reject_coroutine(value: T) -> T:
    """Refuse a coroutine or async generator result: its body would never run here."""
    if inspect.iscoroutine(value):
        value.close()  # else it warns later as never awaited
        raise TypeError(f"the call returned a coroutine: {_ASYNC_HINT}")
    if inspect.isasyncgen(value):
        raise TypeError(f"the call returned an async generator: {_ASYNC_HINT}")
    return value
