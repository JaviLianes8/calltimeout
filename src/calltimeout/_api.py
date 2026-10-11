"""Public entry point: run a callable under a wall-clock timeout."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from enum import Enum
from typing import Final, Literal, TypeVar, overload

from ._errors import CallTimeout
from ._process import run_in_process
from ._thread import run_in_thread

T = TypeVar("T")
D = TypeVar("D")

Mode = Literal["thread", "process"]


class _Unset(Enum):
    token = 0


_UNSET: Final = _Unset.token


@overload
def run(
    fn: Callable[..., T],
    timeout: float,
    *,
    args: tuple[object, ...] = ...,
    kwargs: Mapping[str, object] | None = ...,
    mode: Mode = ...,
) -> T: ...


@overload
def run(
    fn: Callable[..., T],
    timeout: float,
    *,
    args: tuple[object, ...] = ...,
    kwargs: Mapping[str, object] | None = ...,
    mode: Mode = ...,
    default: D,
) -> T | D: ...


def run(
    fn: Callable[..., T],
    timeout: float,
    *,
    args: tuple[object, ...] = (),
    kwargs: Mapping[str, object] | None = None,
    mode: Mode = "thread",
    default: D | _Unset = _UNSET,
) -> T | D:
    """Run fn and return its result, or handle the timeout.

    With mode "thread" the call shares this process and cannot be killed if it
    ignores the clock. With mode "process" the call runs in a child process that is
    terminated on overrun, at the cost of needing picklable arguments and result.

    If default is given it is returned on timeout; otherwise CallTimeout is raised.
    """
    if timeout < 0:
        raise ValueError("timeout must not be negative")
    kw: Mapping[str, object] = kwargs or {}
    try:
        if mode == "thread":
            return run_in_thread(fn, timeout, args, kw)
        if mode == "process":
            return run_in_process(fn, timeout, args, kw)
    except CallTimeout:
        if not isinstance(default, _Unset):
            return default
        raise
    raise ValueError(f"unknown mode: {mode!r}")
