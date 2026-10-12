"""Decorator form of run that keeps the wrapped function's signature."""

from __future__ import annotations

import functools
import sys
from collections.abc import Callable
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
    target: object = sys.modules.get(getattr(obj, "__module__", None) or "")
    for part in str(getattr(obj, "__qualname__", "<>")).split("."):
        target = getattr(target, part, None)
    return target


def _process_target(wrapper: Callable[..., R], fn: Callable[..., R]) -> Callable[..., R]:
    # The wrapper is sent when its name leads to it (the child then unwraps it); when
    # the name still leads to the original (fast = with_timeout(...)(slow)), the
    # original is sent. Under fork nothing is pickled and either works.
    if _by_name(wrapper) is not wrapper and _by_name(fn) is fn:
        return fn
    return wrapper


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
    timed-out call returns it instead of raising. In process mode, under the spawn and
    forkserver start methods, the child imports the function by name, so the decorated
    function or the original must be reachable under its own module and name.
    """
    check_timeout(timeout)
    check_mode(mode, RUNNERS)

    def decorate(fn: Callable[P, T]) -> Callable[P, T | D]:
        check_call(fn, (), None)

        @functools.wraps(fn)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T | D:
            if mode == "process" and claim_child_target(wrapper):
                # Already inside the child started for this call: run the body.
                return fn(*args, **kwargs)
            target = _process_target(wrapper, fn) if mode == "process" else fn
            if isinstance(default, _Unset):
                return run(target, timeout, args=args, kwargs=kwargs, mode=mode)
            return run(target, timeout, args=args, kwargs=kwargs, mode=mode, default=default)

        return wrapper

    return decorate
