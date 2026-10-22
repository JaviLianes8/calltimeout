"""Decorator form of run that keeps the wrapped function's signature."""

from __future__ import annotations

import functools
import sys
from collections.abc import Callable
from numbers import Real
from typing import ParamSpec, TypeVar, overload

from ._api import RUNNERS, UNSET, Mode, _Unset, run
from ._process import claim_child_target
from ._validate import check_call, check_mode, check_timeout

P = ParamSpec("P")
T = TypeVar("T")
D = TypeVar("D")
R = TypeVar("R")


def _by_name(obj: object) -> object:
    """Whatever pickle would find under obj's module and qualified name, or None."""
    try:
        module, name = getattr(obj, "__module__", None), getattr(obj, "__qualname__", None)
        if not isinstance(module, str) or not isinstance(name, str):
            return None
        target: object = sys.modules.get(module)
        for part in name.split("."):
            target = getattr(target, part, None)
    except Exception:
        return None
    return target


def _process_target(wrapper: Callable[..., R], fn: Callable[..., R]) -> Callable[..., R]:
    # The wrapper is sent when its name leads to it (the child then unwraps it).
    # Otherwise the original is sent: found by its own name (fast =
    # with_timeout(...)(slow)) or pickled by value (a partial, a callable object). Under
    # fork nothing is pickled and either works.
    return wrapper if _by_name(wrapper) is wrapper else fn


def _keep_metadata(wrapper: Callable[..., object], fn: object) -> None:
    """functools.update_wrapper, skipping attributes whose lookup raises anything."""
    for attr in (*functools.WRAPPER_ASSIGNMENTS, "__dict__"):
        try:
            value = getattr(fn, attr)
            if attr == "__dict__":
                vars(wrapper).update(value)
            else:
                setattr(wrapper, attr, value)
        except Exception:
            continue  # functools.wraps skips AttributeError only; any error is skipped here
    vars(wrapper)["__wrapped__"] = fn


@overload
def with_timeout(
    timeout: float | Real, *, mode: Mode = ...
) -> Callable[[Callable[P, T]], Callable[P, T]]: ...


@overload
def with_timeout(
    timeout: float | Real, *, mode: Mode = ..., default: D
) -> Callable[[Callable[P, T]], Callable[P, T | D]]: ...


def with_timeout(
    timeout: float | Real, *, mode: Mode = "thread", default: D | _Unset = UNSET
) -> Callable[[Callable[P, T]], Callable[P, T | D]]:
    """Decorate a function so every call runs as ``run(fn, timeout, mode=mode)``.

    The decorated function keeps its parameters for type checkers, so every call is
    checked, and its result type becomes ``T | D`` when a default is given. Settings are
    checked when the decorator is made and the function when it is applied, with the
    errors of ``run``; signal mode's platform and main-thread checks run at each call.
    In process mode under the spawn and forkserver start methods the child imports the
    function by name, so the decorated function or the original must be reachable under
    its own module and name, or the original must pickle by value.

    >>> import time
    >>> from calltimeout import with_timeout
    >>> @with_timeout(2.0)
    ... def add(left: int, right: int) -> int:
    ...     return left + right
    >>> add(2, 3)
    5
    >>> @with_timeout(0.05, default=None)
    ... def lookup(key: str) -> str:
    ...     time.sleep(10)
    ...     return key
    >>> print(lookup("id"))
    None
    """
    check_timeout(timeout)
    name = check_mode(mode, RUNNERS)

    def decorate(fn: Callable[P, T]) -> Callable[P, T | D]:
        check_call(fn, (), None)

        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T | D:
            if name == "process" and claim_child_target(wrapper):
                # Already inside the child started for this call: run the body.
                return fn(*args, **kwargs)
            target = _process_target(wrapper, fn) if name == "process" else fn
            if isinstance(default, _Unset):
                return run(target, timeout, args=args, kwargs=kwargs, mode=mode)
            return run(target, timeout, args=args, kwargs=kwargs, mode=mode, default=default)

        _keep_metadata(wrapper, fn)
        return wrapper

    return decorate
