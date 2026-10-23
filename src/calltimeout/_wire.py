"""What comes back from the child, and the errors about what cannot cross the boundary."""

from __future__ import annotations

import contextlib
import pickle
import traceback
from typing import cast

from ._text import LIMIT, call_name, cut

# Characters of an exception's text kept in a message built around it; the full text
# still travels in the chained traceback.
_DETAIL = 300

# Notes kept on a pickling error (newer Pythons add one per level, quoting keys).
_NOTES = 10


class RemoteTraceback(Exception):
    """Carries the child's formatted traceback as the cause of a re-raised error."""

    def __init__(self, text: str) -> None:
        super().__init__(text)
        self.text = text

    def __str__(self) -> str:
        return self.text


def _cut_notes(source: BaseException, target: BaseException) -> None:
    notes = getattr(source, "__notes__", None)
    if isinstance(notes, list) and notes:
        kept = [cut(note) if isinstance(note, str) else "<note>" for note in notes[:_NOTES]]
        if len(notes) > _NOTES:
            kept.append(f"... and {len(notes) - _NOTES} more notes")
        vars(target)["__notes__"] = kept  # what add_note() writes to


def _bounded(problem: Exception) -> Exception:
    """Bound pickle's error, often quoting a value: its text and its notes.

    It is cut in place when its args carry its text. Otherwise (a __str__ of its own,
    args that cannot be set) a RuntimeError naming its type and quoting it stands in.
    """
    try:
        text = str(problem)
    except Exception:
        text = ""
    try:
        if len(text) > _DETAIL:
            problem.args = (cut(text, _DETAIL),)
            if len(str(problem)) > _DETAIL + 3:
                raise ValueError("its text does not come from its args")
        _cut_notes(problem, problem)
        return problem
    except Exception:
        pass
    name = f"{type(problem).__module__}.{type(problem).__qualname__}"
    stand_in = RuntimeError(cut(f"{name}: {text}", _DETAIL))
    with contextlib.suppress(Exception):
        _cut_notes(problem, stand_in)
    return stand_in.with_traceback(problem.__traceback__)


def unsendable(problem: Exception) -> pickle.PicklingError:
    """The documented error for a call that cannot be pickled, its cause pickle's, bounded.

    Raise it with ``raise error from error.__cause__`` outside the handler of problem, so
    the unbounded original is not kept as its context either.
    """
    cause = _bounded(problem)
    detail = _detail(cause, LIMIT)
    error = pickle.PicklingError(f"the call cannot be sent to the child process: {detail}")
    error.__cause__ = cause
    return error


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
