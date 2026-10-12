"""Public entry point: run a callable under a wall-clock timeout."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from enum import Enum
from typing import Final, Literal, TypeVar, overload

from ._errors import CallTimeout, Expired
from ._process import run_in_process
from ._signal import check_signal_mode, run_with_signal
from ._thread import run_in_thread
from ._validate import check_call, check_mode, check_timeout

T = TypeVar("T")
D = TypeVar("D")

Mode = Literal["thread", "process", "signal"]

RUNNERS: Final = {
    "thread": run_in_thread,
    "process": run_in_process,
    "signal": run_with_signal,
}


class _Unset(Enum):
    token = 0


UNSET: Final = _Unset.token


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
    default: D | _Unset = UNSET,
) -> T | D:
    """Run fn and return its result, or handle the timeout.

    mode "thread" (the default) runs fn in a daemon thread and stops waiting on overrun;
    the call itself cannot be killed and keeps running if it ignores the clock.
    mode "process" runs fn in a child process that is terminated on overrun; fn, its
    arguments and its result must be picklable, and a child that dies without a result
    raises CallCrashed. mode "signal" (POSIX, main thread) raises CallTimeout inside fn.

    A zero timeout raises at once without starting fn. If default is given it is
    returned when this call's own budget runs out; otherwise CallTimeout is raised. A
    CallTimeout from a nested call inside fn always propagates.
    """
    seconds = check_timeout(timeout)
    check_call(fn, args, kwargs)
    check_mode(mode, RUNNERS)
    runner = RUNNERS[mode]
    if mode == "signal":
        check_signal_mode()  # before the zero-budget shortcut, so misuse always surfaces
    try:
        if seconds == 0:
            raise Expired
        return runner(fn, seconds, args, dict(kwargs or {}))
    except Expired as expired:
        if not isinstance(default, _Unset):
            return default
        raise CallTimeout(seconds) from expired.__cause__
