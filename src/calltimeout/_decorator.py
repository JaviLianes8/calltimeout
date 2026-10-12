"""Decorator form of run that keeps the wrapped function's signature."""

from __future__ import annotations

import functools
from collections.abc import Callable
from typing import ParamSpec, TypeVar, overload

from ._api import RUNNERS, UNSET, Mode, _Unset, run
from ._process import claim_child_target
from ._validate import check_call, check_timeout

P = ParamSpec("P")
T = TypeVar("T")
D = TypeVar("D")


@overload
def with_timeout(
    timeout: float, *, mode: Mode = ...
) -> Callable[[Callable[P, T]], Callable[P, T]]: ...


@overload
def with_timeout(
    timeout: float, *, mode: Mode = ..., default: D
) -> Callable[[Callable[P, T]], Callable[P, T | D]]: ...


def with_timeout(
    timeout: float, *, mode: Mode = "thread", default: D | _Unset = UNSET
) -> Callable[[Callable[P, T]], Callable[P, T | D]]:
    """Decorate a function so every call runs under run(fn, timeout, mode=...).

    The decorated function keeps its parameters for type checkers. With default, a
    timed-out call returns it instead of raising. In process mode the function must be
    defined at module level so the child process can import it by name.
    """
    check_timeout(timeout)
    if mode not in RUNNERS:
        raise ValueError(f"unknown mode: {mode!r}")

    def decorate(fn: Callable[P, T]) -> Callable[P, T | D]:
        check_call(fn, (), None)

        @functools.wraps(fn)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T | D:
            if mode == "process" and claim_child_target(wrapper):
                # Already inside the child started for this call: run the body.
                return fn(*args, **kwargs)
            # In process mode the wrapper itself is sent: pickle finds it by the
            # wrapped function's name, and the child unwraps it above.
            target = wrapper if mode == "process" else fn
            if isinstance(default, _Unset):
                return run(target, timeout, args=args, kwargs=kwargs, mode=mode)
            return run(target, timeout, args=args, kwargs=kwargs, mode=mode, default=default)

        return wrapper

    return decorate
