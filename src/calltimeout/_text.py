"""Short descriptions of caller values for messages and thread names: bounded, never raising."""

from __future__ import annotations

# Characters of a caller's value or name quoted in a message; longer text is cut.
LIMIT = 60


def cut(text: str, limit: int = LIMIT) -> str:
    """Return text, or its first limit characters followed by "..."."""
    return text if len(text) <= limit else text[:limit] + "..."


def type_name(value: object) -> str:
    """The name of value's type, cut to LIMIT characters."""
    return cut(type(value).__name__)


def shown(value: object) -> str:
    """Show a value in a message: numbers as written, other values by repr, all bounded.

    A huge integer is described by its size, since printing it can fail (the integer
    string limit) or produce megabytes.
    """
    if isinstance(value, int) and int.bit_length(value) > 64:
        return f"an integer of {int.bit_length(value)} bits"
    try:
        text = str(value) if isinstance(value, (int, float)) else repr(value)
    except Exception:
        return f"a {type_name(value)} that cannot be shown"
    return cut(text)


def call_name(fn: object) -> str:
    """The qualified name of a callable (its type's for objects without one), cut."""
    try:
        name = getattr(fn, "__qualname__", None)
    except Exception:
        name = None
    if not isinstance(name, str) or not name:
        name = type(fn).__qualname__
    return cut(name)
