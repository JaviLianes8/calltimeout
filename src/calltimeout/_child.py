"""What a process-mode child runs: load the call, run it, send back its outcome."""

from __future__ import annotations

from collections.abc import Callable
from contextvars import ContextVar
from multiprocessing.connection import Connection
from typing import Generic, TypeVar, cast

from ._parcel import Parcel
from ._validate import reject_coroutine
from ._wire import pack_error, pack_result, unloadable

T = TypeVar("T")
_authorized: ContextVar[object] = ContextVar("calltimeout_decorator_target", default=None)


class DecoratorCall(Generic[T]):
    """Authorize one wrapper bypass for a child started by that wrapper itself."""

    def __init__(self, target: Callable[..., T]) -> None:
        self.target = target
        self.__qualname__ = getattr(target, "__qualname__", "<unnamed callable>")

    def __call__(self, *args: object, **kwargs: object) -> T:
        token = _authorized.set(self.target)
        try:
            return self.target(*args, **kwargs)
        finally:
            _authorized.reset(token)


def claim_child_target(fn: object) -> bool:
    """Consume the explicit authorization carried by a decorator's own process call."""
    if _authorized.get() is fn:
        _authorized.set(None)
        return True
    return False


def _outcome(parcel: Parcel) -> bytes:
    """The call's result or error, pickled as the caller unpacks it."""
    try:
        try:
            # Spawn and forkserver import fn by name here, and rebuild every argument.
            fn, args, kwargs = parcel.open()
        except Exception as problem:
            error = unloadable(problem)
        else:
            return pack_result(reject_coroutine(fn(*args, **kwargs)))
        raise error from error.__cause__  # outside that handler: no unbounded context
    except BaseException as exc:
        return pack_error(exc)


def serve(parcel: Parcel) -> None:
    """The child process's target: run the call and send its outcome down the pipe."""
    if parcel.conn is None:
        return  # the call could not be sent: the caller is stopping this child
    conn = cast(Connection, parcel.conn)
    try:
        conn.send_bytes(_outcome(parcel))
    finally:
        conn.close()
