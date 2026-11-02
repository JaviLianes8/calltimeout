"""Safe transport causes and text helpers for exceptions raised by the callable."""

from __future__ import annotations

import pickle

# Characters kept in a stand-in for an unpicklable exception raised by the callable.
DETAIL = 300

# Only exact standard exception types are safe to construct without caller hooks.
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


def full_type_name(problem: BaseException) -> str:
    """module.qualname of problem's type, or a fixed text when either cannot be read."""
    kind = type(problem)
    try:
        return f"{kind.__module__}.{kind.__qualname__}"
    except Exception:
        return "an exception whose type cannot be named"


def bounded(problem: Exception) -> Exception:
    """Replace transport failures without retaining caller text, notes, frames or chains."""
    for kind in _PLAIN:
        if type(problem) is kind:
            return kind("transport operation failed")
    return RuntimeError("transport operation failed")
