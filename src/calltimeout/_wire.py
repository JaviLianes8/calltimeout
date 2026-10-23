"""What comes back from the child, and the errors about what cannot cross the boundary."""

from __future__ import annotations

import pickle
import traceback
from typing import cast

from ._causes import DETAIL, bounded, exact_text
from ._text import LIMIT, call_name, cut

SENT = "the call cannot be sent to the child process"


class RemoteTraceback(Exception):
    """Carries the child's formatted traceback as the cause of a re-raised error."""

    def __init__(self, text: str) -> None:
        super().__init__(text)
        self.text = text

    def __str__(self) -> str:
        return self.text


def unsendable(problem: Exception) -> pickle.PicklingError:
    """The documented error for a call that cannot be pickled, its cause pickle's, bounded.

    Raise it with ``raise error from error.__cause__`` outside the handler of problem, so
    the unbounded original is not kept as its context either.
    """
    cause = bounded(problem)
    detail = _detail(cause, LIMIT)
    error = pickle.PicklingError(f"{SENT}: {detail}")
    error.__cause__ = cause
    return error


def too_many(passed: int, limit: int) -> pickle.PicklingError:
    """The documented error for a call holding more descriptors than a start can pass."""
    held = f"it holds {passed} descriptors (pipe ends, sockets, two per queue)"
    return pickle.PicklingError(f"{SENT}: {held} and a forkserver start passes at most {limit}")


def _detail(exc: BaseException, limit: int = DETAIL) -> str:
    text = exact_text(exc, repr)
    if text is None:
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
            message = cut(str(exc), DETAIL)
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
    try:
        raise error
    finally:
        # The traceback refers to this frame: holding the error here would make a cycle
        # that keeps the caller's frames, and the child's handles in them, until a collection.
        del error, payload
