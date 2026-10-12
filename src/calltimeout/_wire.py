"""What crosses the process boundary: the call going in, the outcome coming back."""

from __future__ import annotations

import pickle
import traceback
from multiprocessing.reduction import ForkingPickler
from typing import cast


class RemoteTraceback(Exception):
    """Carries the child's formatted traceback as the cause of a re-raised error."""

    def __init__(self, text: str) -> None:
        super().__init__(text)
        self.text = text

    def __str__(self) -> str:
        return self.text


def prepickle(method: str, call: tuple[object, ...]) -> object:
    """Pickle the call before any process exists, so a start cannot fail half way.

    A start that failed while pickling (seen on Windows) left a half-built Popen whose
    finalizer later closed handle numbers reused by the next call's pipe.
    """
    if method == "fork":
        return call  # nothing is pickled
    try:
        return bytes(ForkingPickler.dumps(call))
    except RuntimeError:
        # Locks, queues and the like only pickle inside Process.start(): pass them as is.
        return call


def pack_error(exc: BaseException) -> bytes:
    """Pickle an exception with its traceback text, or a stand-in if it cannot travel."""
    text = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    try:
        data = pickle.dumps((False, exc, text))
        pickle.loads(data)  # an exception can pickle and still fail to rebuild
    except Exception as problem:
        name = f"{type(exc).__module__}.{type(exc).__qualname__}"
        try:
            message = str(exc)
        except Exception:
            message = "<str() failed>"
        stand_in = RuntimeError(f"{name}: {message} (not picklable: {problem!r})")
        data = pickle.dumps((False, stand_in, text))
    return data


def pack_result(value: object) -> bytes:
    """Pickle a result, or a PicklingError explaining why it cannot be sent back."""
    try:
        return pickle.dumps((True, value, ""))
    except Exception as problem:
        return pack_error(
            pickle.PicklingError(f"the call's result cannot be sent back: {problem!r}")
        )


def unpack(data: bytes) -> object:
    """Return the child's result or raise its exception with the child's traceback."""
    try:
        ok, payload, text = pickle.loads(data)
    except Exception as problem:
        raise pickle.UnpicklingError(
            f"the call's result cannot be rebuilt in this process: {problem!r}"
        ) from problem
    if ok:
        return cast(object, payload)
    error = cast(BaseException, payload)
    error.__cause__ = RemoteTraceback(text)
    raise error
