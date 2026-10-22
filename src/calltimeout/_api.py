"""Public entry point: run a callable under a wall-clock timeout."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from enum import Enum
from numbers import Real
from typing import Final, Literal, TypeVar, overload

from ._errors import CallTimeout, Expired
from ._process import run_in_process
from ._signal import check_signal_mode, run_with_signal
from ._thread import run_in_thread
from ._validate import check_call, check_mode, check_timeout

T = TypeVar("T")
D = TypeVar("D")

Mode = Literal["thread", "process", "signal"]
Mode.__doc__ = """The names of the three mechanisms ``run`` and ``with_timeout`` accept.

Use it to annotate your own wrappers, so type checkers reject any other name.

>>> from typing import get_args
>>> from calltimeout import Mode, run
>>> def quick(mode: Mode) -> int:
...     return run(pow, 5.0, args=(2, 3), mode=mode)
>>> get_args(Mode)
('thread', 'process', 'signal')
>>> quick("thread")
8
"""

RUNNERS: Final = {
    "thread": run_in_thread,
    "process": run_in_process,
    "signal": run_with_signal,
}


class _Unset(Enum):
    """Marks an argument that was not given: None is a valid default."""

    token = 0

    def __repr__(self) -> str:
        return "<no default>"


UNSET: Final = _Unset.token


@overload
def run(
    fn: Callable[..., T],
    timeout: float | Real,
    *,
    args: tuple[object, ...] = ...,
    kwargs: Mapping[str, object] | None = ...,
    mode: Mode = ...,
) -> T: ...


@overload
def run(
    fn: Callable[..., T],
    timeout: float | Real,
    *,
    args: tuple[object, ...] = ...,
    kwargs: Mapping[str, object] | None = ...,
    mode: Mode = ...,
    default: D,
) -> T | D: ...


def run(
    fn: Callable[..., T],
    timeout: float | Real,
    *,
    args: tuple[object, ...] = (),
    kwargs: Mapping[str, object] | None = None,
    mode: Mode = "thread",
    default: D | _Unset = UNSET,
) -> T | D:
    """Call ``fn(*args, **kwargs)`` and return its result, or give up after timeout seconds.

    ``mode`` picks the mechanism. ``"thread"`` (the default) runs fn in a daemon thread
    and stops waiting on overrun, but cannot stop the call itself. ``"process"`` runs fn
    in a child process that is terminated on overrun; fn, its arguments and its result
    must pickle, and a child that dies without a result raises ``CallCrashed``.
    ``"signal"`` (POSIX, main thread only) raises ``CallTimeout`` inside fn.

    ``timeout`` is a number of seconds (an int, float or other real number; not a bool,
    NaN or negative); zero raises at once without starting fn. When the budget runs out
    ``CallTimeout`` is raised, or ``default`` is returned if one is given. An exception
    raised by fn reaches the caller, and a ``CallTimeout`` from a nested call inside fn
    always propagates. Bad arguments raise ``TypeError`` or ``ValueError`` before
    anything starts; in process mode a call that cannot be pickled raises
    ``pickle.PicklingError`` before any process starts.

    >>> import math, time
    >>> from calltimeout import CallTimeout, run
    >>> run(pow, 5.0, args=(2, 10))
    1024
    >>> run(time.sleep, 0.05, args=(10,), default="gave up")
    'gave up'
    >>> try:
    ...     run(time.sleep, 0.05, args=(10,))
    ... except CallTimeout as error:
    ...     print(error)
    call did not finish within 0.05 seconds
    >>> run(math.factorial, 30.0, args=(20,), mode="process")
    2432902008176640000
    """
    seconds = check_timeout(timeout)
    check_call(fn, args, kwargs)
    name = check_mode(mode, RUNNERS)
    runner = RUNNERS[name]
    if name == "signal":
        check_signal_mode()  # before the zero-budget shortcut, so misuse always surfaces
    try:
        if seconds == 0:
            raise Expired
        return runner(fn, seconds, args, {} if kwargs is None else dict(kwargs))
    except Expired as expired:
        if not isinstance(default, _Unset):
            return default
        raise CallTimeout(seconds) from expired.__cause__
