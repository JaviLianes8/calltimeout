"""What comes back from the child, and the errors about what cannot cross the boundary."""

from __future__ import annotations

import pickle
import traceback
from typing import TypeVar, cast

from ._causes import DETAIL, bounded, exact_text, full_type_name
from ._errors import RemoteTraceback
from ._text import LIMIT, call_name, cut

SENT = "the call cannot be sent to the child process"
SENT_BACK = "the call's result cannot be sent back"
REBUILT = "the call's result cannot be rebuilt in this process"

E = TypeVar("E", bound=pickle.PickleError)


def _about(kind: type[E], what: str, problem: Exception) -> E:
    """A documented pickling error quoting pickle's, which is bounded and chained as its cause.

    Raise it with ``raise error from error.__cause__`` outside the handler of problem, so
    the unbounded original is not kept as its context either.
    """
    cause = bounded(problem)
    error = kind(f"{what}: {_detail(cause, LIMIT)}")
    error.__cause__ = cause
    return error


def unsendable(problem: Exception) -> pickle.PicklingError:
    """The documented error for a call that cannot be pickled (see _about)."""
    return _about(pickle.PicklingError, SENT, problem)


def too_many(passed: int, limit: int) -> pickle.PicklingError:
    """The documented error for a call holding more descriptors than a start can pass."""
    kinds = "pipe ends, sockets, two per queue, one per shared-memory block"
    held = f"it holds {passed} descriptors ({kinds})"
    return pickle.PicklingError(f"{SENT}: {held} and a forkserver start passes at most {limit}")


def _detail(exc: BaseException, limit: int = DETAIL) -> str:
    text = exact_text(exc, repr)
    if text is None:
        text = f"<{call_name(type(exc))} whose repr failed>"
    return cut(text, limit)


def _formatted(exc: BaseException) -> str:
    try:
        return "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    except Exception as problem:
        # Its type's own attributes can raise: the error is still sent, without the text.
        return f"<the child's traceback could not be formatted: {_detail(problem)}>\n"


def pack_error(exc: BaseException) -> bytes:
    """Pickle an exception with its traceback text, or a stand-in if it cannot travel."""
    text = _formatted(exc)
    try:
        data = pickle.dumps((False, exc, text))
        pickle.loads(data)  # an exception can pickle and still fail to rebuild
    except Exception as problem:
        try:
            message = cut(str(exc), DETAIL)
        except Exception:
            message = "<str() failed>"
        name = cut(full_type_name(exc))
        stand_in = RuntimeError(f"{name}: {message} (not picklable: {_detail(problem)})")
        data = pickle.dumps((False, stand_in, text))
    return data


def pack_result(value: object) -> bytes:
    """Pickle a result, or a PicklingError explaining why it cannot be sent back."""
    try:
        return pickle.dumps((True, value, ""))
    except Exception as problem:
        error = _about(pickle.PicklingError, SENT_BACK, problem)
    try:
        # Raised, so the traceback text sent along shows where pickling failed (the
        # bounded cause keeps its frames and the notes newer Pythons add about which item).
        raise error from error.__cause__
    except pickle.PicklingError as raised:
        return pack_error(raised)


def _load(data: bytes) -> tuple[bool, object, str]:
    try:
        return cast("tuple[bool, object, str]", pickle.loads(data))
    except Exception as problem:
        error = _about(pickle.UnpicklingError, REBUILT, problem)
    try:
        raise error from error.__cause__
    finally:
        del error  # no cycle through this frame


def unpack(data: bytes) -> object:
    """Return the child's result or raise its exception with the child's traceback."""
    ok, payload, text = _load(data)
    if ok:
        return payload
    error = cast(BaseException, payload)
    error.__cause__ = RemoteTraceback(text)
    try:
        raise error
    finally:
        # The traceback refers to this frame: holding the error here would make a cycle
        # that keeps the caller's frames, and the child's handles in them, until a collection.
        del error, payload
