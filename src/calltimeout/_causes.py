"""Pickle's error about a call, bounded before it is chained to the documented error."""

from __future__ import annotations

import contextlib
import pickle
from typing import Any, cast

from ._text import cut

# Characters of an exception's text kept in a message built around it, or in the bounded
# error chained to one.
DETAIL = 300

# Notes kept on a pickling error (newer Pythons add one per level, quoting keys).
_NOTES = 10

# Exceptions whose text comes only from their args, as pickle raises them. Any other type
# (an argument's own reduce can raise anything) may produce its text, notes or chain in
# ways that cannot be bounded in place, so a stand-in replaces it.
_PLAIN = (
    Exception,
    TypeError,
    ValueError,
    RuntimeError,
    RecursionError,
    NotImplementedError,
    AttributeError,
    LookupError,
    IndexError,
    OverflowError,
    EOFError,
    pickle.PickleError,
    pickle.PicklingError,
)

# Read through BaseException itself, so a subclass cannot hand out something else.
_DICT: Any = BaseException.__dict__["__dict__"]
_TRACEBACK: Any = BaseException.__dict__["__traceback__"]


def exact_text(value: object, show: Any = str) -> str | None:
    """show(value) read once, as a plain str (a subclass could lie about its length)."""
    try:
        text = show(value)
        return str.__str__(text) if isinstance(text, str) else None
    except Exception:
        return None


def _notes(notes: object) -> list[str] | None:
    if type(notes) is str:
        notes = [notes]
    if type(notes) is not list and type(notes) is not tuple:
        return None  # nothing traceback could print in a bounded way
    every = cast("list[object] | tuple[object, ...]", notes)
    kept = [
        cut(str.__str__(item)) if isinstance(item, str) else "<note>" for item in every[:_NOTES]
    ]
    if len(every) > _NOTES:
        kept.append(f"... and {len(every) - _NOTES} more notes")
    return kept


def _cut_notes(source: BaseException, target: BaseException) -> None:
    kept = _notes(_DICT.__get__(source).get("__notes__"))
    own = _DICT.__get__(target)
    own.pop("__notes__", None)
    if kept:
        own["__notes__"] = kept  # what add_note() writes to


def full_type_name(problem: BaseException) -> str:
    """module.qualname of problem's type, or a fixed text when either cannot be read."""
    kind = type(problem)
    try:
        return f"{kind.__module__}.{kind.__qualname__}"
    except Exception:
        return "an exception whose type cannot be named"


def bounded(problem: Exception) -> Exception:
    """Bound pickle's error, often quoting a value: its text, its notes and its chain.

    A plain error (one of _PLAIN, exactly) is cut in place. Any other is replaced by a
    RuntimeError naming its type and quoting its text, read once. Neither keeps the
    errors chained to it: they can quote a value too.
    """
    text = exact_text(problem)
    shown = "<str() failed>" if text is None else text
    if any(type(problem) is plain for plain in _PLAIN):
        try:
            args = problem.args
            if text is None or len(text) > DETAIL or len(args) != 1 or type(args[0]) is not str:
                # Its text then comes from this one plain str, whatever its args were.
                problem.args = (cut(shown, DETAIL),)
            _cut_notes(problem, problem)
            problem.__cause__ = problem.__context__ = None
            return problem
        except Exception:
            pass  # a plain type does not fail here; the stand-in is the fallback
    stand_in = RuntimeError(cut(f"{full_type_name(problem)}: {shown}", DETAIL))
    with contextlib.suppress(Exception):
        _cut_notes(problem, stand_in)
    with contextlib.suppress(Exception):
        stand_in = stand_in.with_traceback(_TRACEBACK.__get__(problem))
    return stand_in
