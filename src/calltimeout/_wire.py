"""What crosses the process boundary: the call going in, the outcome coming back."""

from __future__ import annotations

import io
import pickle
import traceback
from multiprocessing.context import assert_spawning
from multiprocessing.reduction import ForkingPickler
from typing import Any, cast

from ._text import call_name, cut

# Characters of an exception's text kept in a message built around it; the full text
# still travels in the chained traceback.
_DETAIL = 300

# Notes kept on a pickling error (newer Pythons add one per level, quoting keys).
_NOTES = 10

# Objects of one call that may only pickle inside Process.start() (locks, queues).
_SKIPS = 100


class RemoteTraceback(Exception):
    """Carries the child's formatted traceback as the cause of a re-raised error."""

    def __init__(self, text: str) -> None:
        super().__init__(text)
        self.text = text

    def __str__(self) -> str:
        return self.text


def _start_only(problem: Exception) -> list[object]:
    """[the object] if problem is multiprocessing refusing one outside Process.start()."""
    tb = problem.__traceback__
    while tb is not None and tb.tb_next is not None:
        tb = tb.tb_next
    if type(problem) is not RuntimeError or tb is None:
        return []
    frame = tb.tb_frame
    if frame.f_code is not assert_spawning.__code__ or "obj" not in frame.f_locals:
        return []
    return [frame.f_locals["obj"]]


class _DryRun(ForkingPickler):
    """Pickles a call with the objects that only pickle inside Process.start() left out."""

    def __init__(self, file: io.BytesIO, skipped: list[object]) -> None:
        super().__init__(file)
        self.skipped = {id(each) for each in skipped}

    def reducer_override(self, obj: Any) -> Any:
        return (int, ()) if id(obj) in self.skipped else NotImplemented


def _unsendable(problem: Exception) -> pickle.PicklingError:
    """The documented error for a call that cannot be pickled, with bounded notes."""
    notes = getattr(problem, "__notes__", None)
    if isinstance(notes, list) and notes:
        kept = [cut(note) if isinstance(note, str) else "<note>" for note in notes[:_NOTES]]
        if len(notes) > _NOTES:
            kept.append(f"... and {len(notes) - _NOTES} more notes")
        vars(problem)["__notes__"] = kept  # what add_note() writes to
    return pickle.PicklingError(f"the call cannot be sent to the child process: {_detail(problem)}")


def prepickle(method: str, call: tuple[object, ...]) -> object:
    """Pickle the call before any process exists, so a start cannot fail half way.

    A start that failed while pickling (seen on Windows) left a half-built Popen whose
    finalizer later closed handle numbers reused by the next call's pipe. Raises
    pickle.PicklingError, chained from pickle's own error, for a call that cannot pickle.
    """
    if method == "fork":
        return call  # nothing is pickled
    skipped: list[object] = []
    while True:
        try:
            if not skipped:
                return bytes(ForkingPickler.dumps(call))
            _DryRun(io.BytesIO(), skipped).dump(call)
            # Locks, queues and the like only pickle inside Process.start(), and the rest
            # of the call pickles: pass it as is.
            return call
        except Exception as problem:
            found = _start_only(problem)
            # Each round leaves out one more object of the call; one refused again (or a
            # reduce that keeps making new ones) ends the search.
            if not found or len(skipped) >= _SKIPS or any(found[0] is x for x in skipped):
                raise _unsendable(problem) from problem
            skipped += found


def _detail(exc: BaseException) -> str:
    try:
        text = repr(exc)
    except Exception:
        text = f"<{call_name(type(exc))} whose repr failed>"
    return cut(text, _DETAIL)


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
