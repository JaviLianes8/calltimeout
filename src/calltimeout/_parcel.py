"""The call as the child receives it, pickled before any process exists."""

from __future__ import annotations

import io
import pickle
import socket
from collections.abc import Callable
from multiprocessing import connection
from multiprocessing.context import get_spawning_popen, set_spawning_popen
from multiprocessing.managers import BaseProxy
from multiprocessing.reduction import ForkingPickler
from typing import Any, cast

from ._handoff import dumps_for_child
from ._wire import too_many, unsendable

# Pickled outside Process.start(), a pipe end or socket is duplicated for a child that may
# never take it (the duplicate then stays open here) and a proxy loses its authkey.
_HANDLES: frozenset[object] = frozenset(
    {socket.socket, connection.Connection, getattr(connection, "PipeConnection", None)}
) - {None}  # PipeConnection is Windows only

# A forkserver start sends the child's descriptors to the fork server in one message. Linux
# carries at most 253 in one (SCM_MAX_FD): the server adds 4 and the start the result pipe.
FORKSERVER_LIMIT = 248

Call = tuple[Callable[..., object], tuple[object, ...], dict[str, Any]]


def _take(index: int) -> object:
    """Stands in the call's bytes for an object only Process.start() may pickle."""
    raise RuntimeError(f"held object {index} is only rebuilt by Parcel.open()")


def _is_closed(end: Any) -> bool:
    try:
        return bool(end.fileno() < 0)  # a closed socket gives -1
    except OSError:
        return True  # a closed pipe end raises


class _Rehearsal:
    """Stands in for the Popen of a start, so locks and queues pickle as they would there.

    Nothing is duplicated for a child: what the rehearsal pickles is thrown away. It counts
    the handles the start would pass.
    """

    def __init__(self) -> None:
        self.passed = 0

    def duplicate_for_child(self, handle: int) -> int:
        self.passed += 1
        return handle

    def DupFd(self, fd: int) -> int:
        return fd


class _Trial(ForkingPickler):
    """Pickles a call, holding back what only Process.start() may pickle.

    Each pipe end, socket and proxy is checked and replaced by its index among them.
    """

    def __init__(self) -> None:
        self.buffer = io.BytesIO()
        super().__init__(self.buffer)
        self.held: list[object] = []

    def reducer_override(self, obj: Any) -> Any:
        kind = type(obj)  # not obj.__class__, which runs the caller's code
        if kind in _HANDLES:
            if _is_closed(obj):
                raise ValueError(f"cannot send a closed {kind.__name__}")
        elif not issubclass(kind, BaseProxy):
            return NotImplemented
        self.held.append(obj)
        return (_take, (len(self.held) - 1,))


def _descriptors(held: list[object]) -> int:
    return sum(type(obj) in _HANDLES for obj in held)


def _rehearse(call: Call) -> int:
    """Pickle the call as Process.start() will, with every lock and queue in it.

    Returns how many descriptors the start will pass to the child.
    """
    previous = get_spawning_popen()
    rehearsal, trial = _Rehearsal(), _Trial()
    set_spawning_popen(cast(Any, rehearsal))
    try:
        trial.dump(call)
    except Exception as problem:
        error = unsendable(problem)
    else:
        return rehearsal.passed + _descriptors(trial.held)
    finally:
        set_spawning_popen(previous)
    try:
        raise error from error.__cause__
    finally:
        del error  # no cycle through this frame


def prepickle(method: str, call: Call) -> tuple[bytes | None, tuple[object, ...]]:
    """Pickle the call before any process exists, so a start cannot fail half way.

    A start that failed while pickling (seen on Windows) left a half-built Popen whose
    finalizer later closed handle numbers reused by the next call's pipe. Raises
    pickle.PicklingError, chained from pickle's own error, for a call that cannot pickle,
    and for one holding more descriptors than a forkserver start can pass. Returns the
    call's bytes and the objects held back from them, for the start to pickle; or no bytes
    and the call itself, when it holds objects that only pickle inside a start (locks,
    queues), once a rehearsal proved it pickles there.
    """
    if method == "fork":
        return None, call  # nothing is pickled
    trial = _Trial()
    try:
        trial.dump(call)
    except Exception:
        pass  # rehearsed below, outside this handler, so its error has no context
    else:
        _check_passed(method, _descriptors(trial.held))
        return trial.buffer.getvalue(), tuple(trial.held)
    # Most likely a lock or queue refusing to pickle outside a start: rehearse one,
    # which also raises the documented error when something else is wrong.
    _check_passed(method, _rehearse(call))
    return None, call


def _check_passed(method: str, passed: int) -> None:
    if method == "forkserver" and passed > FORKSERVER_LIMIT:
        raise too_many(passed, FORKSERVER_LIMIT)  # checked here, as a failed start is not clean


class _Unsealer(pickle.Unpickler):
    def __init__(self, data: bytes, held: tuple[object, ...]) -> None:
        super().__init__(io.BytesIO(data))
        self.held = held

    def find_class(self, module: str, name: str, /) -> Any:
        if module == __name__ and name == "_take":
            return self.held.__getitem__
        return super().find_class(module, name)


class Parcel:
    """The call and the result pipe's write end, as Process.start() hands them over."""

    def __init__(
        self, conn: Any, data: bytes | None, held: tuple[object, ...], loaded: bytes = b""
    ) -> None:
        self.conn = conn
        self.data = data
        self.held = held
        self.loaded = loaded
        self.refused: BaseException | None = None

    def __reduce__(self) -> tuple[object, ...]:
        # Runs inside Process.start(): the held objects go to the child it created. The
        # write end travels apart, so the child can report a call it fails to load.
        try:
            held = dumps_for_child(self.held)
        except BaseException as problem:
            # Raised here, it would leave a half-built Popen (see prepickle), even for a
            # KeyboardInterrupt. The start finishes instead, and the caller stops the child
            # before it runs anything, then raises the documented error or this one.
            self.refused = problem
            return (Parcel, (None, None, ()))
        return (_arrived, (dumps_for_child(self.conn), self.data, held))

    def open(self) -> Call:
        """Rebuild the call in the child."""
        held = cast(tuple[object, ...], pickle.loads(self.loaded)) if self.loaded else self.held
        if self.data is None:
            return cast(Call, held)
        return cast(Call, _Unsealer(self.data, held).load())


def _arrived(conn: bytes, data: bytes | None, held: bytes) -> Parcel:
    return Parcel(pickle.loads(conn), data, (), held)
