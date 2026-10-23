"""What crosses the process boundary: the call going in, the outcome coming back."""

from __future__ import annotations

import io
import pickle
import socket
import traceback
from multiprocessing import connection
from multiprocessing.context import get_spawning_popen, set_spawning_popen
from multiprocessing.reduction import ForkingPickler
from typing import Any, cast

from ._text import LIMIT, call_name, cut

# Characters of an exception's text kept in a message built around it; the full text
# still travels in the chained traceback.
_DETAIL = 300

# Notes kept on a pickling error (newer Pythons add one per level, quoting keys).
_NOTES = 10

# Objects whose pickling outside Process.start() duplicates an OS handle for a child that
# may never take it: the duplicate then stays open in this process.
_HANDLES: tuple[type, ...] = (
    socket.socket,
    connection.Connection,
    getattr(connection, "PipeConnection", connection.Connection),  # Windows only
)


class RemoteTraceback(Exception):
    """Carries the child's formatted traceback as the cause of a re-raised error."""

    def __init__(self, text: str) -> None:
        super().__init__(text)
        self.text = text

    def __str__(self) -> str:
        return self.text


class _Rehearsal:
    """Stands in for the Popen of a start, so locks and queues pickle as they would there.

    Nothing is duplicated for a child: what the rehearsal pickles is thrown away.
    """

    def duplicate_for_child(self, handle: int) -> int:
        return handle

    def DupFd(self, fd: int) -> int:
        return fd


class _Trial(ForkingPickler):
    """Pickles a call with pipes and sockets checked but left out, so none is duplicated."""

    def __init__(self) -> None:
        self.buffer = io.BytesIO()
        super().__init__(self.buffer)
        self.handles = False

    def reducer_override(self, obj: Any) -> Any:
        if not isinstance(obj, _HANDLES):
            return NotImplemented
        if cast(Any, obj).fileno() < 0:  # a closed pipe raises, a closed socket gives -1
            raise OSError(f"cannot send a closed {type(obj).__name__}")
        self.handles = True
        return (int, ())


def _bounded(problem: Exception) -> Exception:
    """Bound pickle's error in place: its text, often quoting a value, and its notes."""
    try:
        text = str(problem)
    except Exception:
        text = ""
    if len(text) > _DETAIL and len(problem.args) == 1:
        problem.args = (cut(text, _DETAIL),)
    notes = getattr(problem, "__notes__", None)
    if isinstance(notes, list) and notes:
        kept = [cut(note) if isinstance(note, str) else "<note>" for note in notes[:_NOTES]]
        if len(notes) > _NOTES:
            kept.append(f"... and {len(notes) - _NOTES} more notes")
        vars(problem)["__notes__"] = kept  # what add_note() writes to
    return problem


def _unsendable(problem: Exception) -> pickle.PicklingError:
    """The documented error for a call that cannot be pickled."""
    detail = _detail(_bounded(problem), LIMIT)
    return pickle.PicklingError(f"the call cannot be sent to the child process: {detail}")


def _rehearse(call: tuple[object, ...]) -> None:
    """Pickle the call as Process.start() will, with every lock and queue in it."""
    previous = get_spawning_popen()
    set_spawning_popen(cast(Any, _Rehearsal()))
    try:
        _Trial().dump(call)
    except Exception as problem:
        raise _unsendable(problem) from problem
    finally:
        set_spawning_popen(previous)


def prepickle(method: str, call: tuple[object, ...]) -> object:
    """Pickle the call before any process exists, so a start cannot fail half way.

    A start that failed while pickling (seen on Windows) left a half-built Popen whose
    finalizer later closed handle numbers reused by the next call's pipe. Raises
    pickle.PicklingError, chained from pickle's own error, for a call that cannot pickle.
    Returns the bytes the child loads, or the call itself when it holds objects that only
    pickle inside Process.start() (locks, queues), once a rehearsal proved it pickles.
    """
    if method == "fork":
        return call  # nothing is pickled
    trial = _Trial()
    try:
        trial.dump(call)
    except Exception:
        # Most likely a lock or queue refusing to pickle outside a start: rehearse one,
        # which also raises the documented error when something else is wrong.
        _rehearse(call)
        return call
    if not trial.handles:
        return trial.buffer.getvalue()
    try:
        # Pipes and sockets are duplicated once, for the child that takes them.
        return bytes(ForkingPickler.dumps(call))
    except Exception as problem:
        raise _unsendable(problem) from problem


def _detail(exc: BaseException, limit: int = _DETAIL) -> str:
    try:
        text = repr(exc)
    except Exception:
        text = f"<{call_name(type(exc))} whose repr failed>"
    return cut(text, limit)


def pack_error(exc: BaseException) -> bytes:
    """Pickle an exception with its traceback text, or a stand-in if it cannot travel."""
    text = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    try:
        data = pickle.dumps((False, exc, text))
        pickle.loads(data)  # an exception can pickle and still fail to rebuild
    except Exception as problem:
        name = f"{type(exc).__module__}.{type(exc).__qualname__}"
        try:
            message = cut(str(exc), _DETAIL)
        except Exception:
            message = "<str() failed>"
        stand_in = RuntimeError(f"{cut(name)}: {message} (not picklable: {_detail(problem)})")
        data = pickle.dumps((False, stand_in, text))
    return data


def pack_result(value: object) -> bytes:
    """Pickle a result, or a PicklingError explaining why it cannot be sent back."""
    try:
        return pickle.dumps((True, value, ""))
    except Exception as problem:
        try:
            # Raised from the problem, so the traceback text sent along shows where
            # pickling failed (and the notes newer Pythons add about which item).
            message = f"the call's result cannot be sent back: {_detail(problem)}"
            raise pickle.PicklingError(message) from problem
        except pickle.PicklingError as error:
            return pack_error(error)


def unpack(data: bytes) -> object:
    """Return the child's result or raise its exception with the child's traceback."""
    try:
        ok, payload, text = pickle.loads(data)
    except Exception as problem:
        message = f"the call's result cannot be rebuilt in this process: {_detail(problem)}"
        raise pickle.UnpicklingError(message) from problem
    if ok:
        return cast(object, payload)
    error = cast(BaseException, payload)
    error.__cause__ = RemoteTraceback(text)
    raise error
