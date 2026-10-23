"""A module whose lazy __getattr__ raises ImportError for the plain names it lacks."""

from __future__ import annotations


class Double:
    """A callable object, pickled by value."""

    def __call__(self, value: int) -> int:
        return value * 2


def __getattr__(name: str) -> object:
    if name.startswith("__"):
        raise AttributeError(name)  # tools probing dunders (pytest, inspect) expect this
    raise ImportError(f"lazy attribute {name} is not available")
