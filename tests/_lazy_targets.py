"""A module with lazy attributes whose loading raises ImportError instead of AttributeError."""

from __future__ import annotations

# Names this module would load on first use; here loading them fails. The decorator looks
# the wrapper up by its qualified name, which starts with with_timeout.
_LAZY = frozenset({"with_timeout", "helpers"})


class Double:
    """A callable object, pickled by value."""

    def __call__(self, value: int) -> int:
        return value * 2


def __getattr__(name: str) -> object:
    if name in _LAZY:
        raise ImportError(f"lazy attribute {name} is not available")
    raise AttributeError(name)
