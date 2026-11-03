"""Short descriptions of caller values for messages and thread names: bounded, never raising."""

from __future__ import annotations

# Characters of a caller's value or name quoted in a message; longer text is cut.
LIMIT = 60

# Stand-ins for a name that cannot be read, or that is not text.
UNNAMED_TYPE = "<unnamed type>"
UNNAMED_CALL = "<unnamed callable>"


def cut(text: str, limit: int = LIMIT) -> str:
    """Return text, or its first limit characters followed by "...".

    Measured as a plain str: a subclass could lie about its length.
    """
    text = str.__str__(text)
    return text if len(text) <= limit else text[:limit] + "..."


def _name(owner: object, attribute: str) -> str | None:
    """owner's attribute if it is text, cut; None if it is not text or reading it raised."""
    try:
        name = getattr(owner, attribute, None)
        return cut(name) if isinstance(name, str) and str.__len__(name) else None
    except Exception:
        return None  # also an object that only claims to be a str


def type_name(value: object) -> str:
    """The name of value's type, cut to LIMIT characters."""
    return _name(type(value), "__name__") or UNNAMED_TYPE


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
    return _name(fn, "__qualname__") or _name(type(fn), "__qualname__") or UNNAMED_CALL
