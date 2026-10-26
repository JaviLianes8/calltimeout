"""Results that cannot cross back to the caller, at module level for spawn and forkserver."""

from __future__ import annotations

from _wire_targets import RaisesOnReduce


def noted_unpicklable(count: int, size: int) -> object:
    # Set directly rather than with add_note(), which Python 3.10 lacks.
    error = ValueError("cannot pickle this result")
    vars(error)["__notes__"] = ["n" * size for _ in range(count)]
    return RaisesOnReduce(error)


def huge_unpicklable(size: int) -> object:
    error = ValueError("v" * size)
    vars(error)["__notes__"] = ["n" * size]
    try:
        raise ValueError("w" * size)
    except ValueError as context:
        error.__context__ = context
    return RaisesOnReduce(error)
