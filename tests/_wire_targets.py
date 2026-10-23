"""Targets for the pickling contracts, at module level so spawn and forkserver import them."""

from __future__ import annotations

import multiprocessing
import threading
from typing import Any


def process_name() -> str:
    return multiprocessing.current_process().name


def thread_name() -> str:
    return threading.current_thread().name


class RaisesOnReduce:
    """An object whose pickling raises the given exception."""

    def __init__(self, error: Exception) -> None:
        self.error = error

    def __reduce__(self) -> tuple[object, ...]:
        raise self.error


def unpicklable_with_text(size: int) -> object:
    return RaisesOnReduce(ValueError("x" * size))


def fail_to_load(size: int) -> object:
    raise ValueError("y" * size)


class LoadsBadly:
    """Pickles in the child; rebuilding it in the parent raises a huge error."""

    def __init__(self, size: int) -> None:
        self.size = size

    def __reduce__(self) -> tuple[object, tuple[int]]:
        return (fail_to_load, (self.size,))


def unrebuildable_with_text(size: int) -> object:
    return LoadsBadly(size)


def nested(depth: int) -> list[object]:
    value: list[object] = []
    for _ in range(depth):
        value = [value]
    return value


class Strict:
    """A working callable whose __getattr__ raises something other than AttributeError."""

    def __call__(self) -> str:
        return "ran"

    def __getattr__(self, name: str) -> object:
        raise LookupError(f"no attribute {name}" + "z" * 5_000)


class Multiply:
    """A callable object, pickled by value."""

    def __init__(self, factor: int) -> None:
        self.factor = factor

    def __call__(self, value: int) -> int:
        return value * self.factor


def count(*args: object) -> int:
    return len(args)


def write_and_close(conn: Any, *others: object) -> str:
    conn.send("hello")
    conn.close()
    return "sent"


class RefusesLikeAssertSpawning:
    """Raises RuntimeError from a frame holding a local named obj, as assert_spawning does."""

    def __reduce__(self) -> tuple[object, ...]:
        obj = self
        raise RuntimeError(f"this object refuses to be pickled: {type(obj).__name__}")


REDUCED: list[int] = []


class Counted:
    """Counts how many times the caller pickles it."""

    def __reduce__(self) -> tuple[object, ...]:
        REDUCED.append(1)
        return (Counted, ())


class SecretToken:
    """Its repr holds a secret, and pickling it fails with pickle quoting that repr."""

    def __init__(self, secret: str) -> None:
        self.secret = secret

    def __repr__(self) -> str:
        return f"SecretToken({self.secret!r})"

    def __reduce__(self) -> str:
        return "NO_SUCH_GLOBAL_IN_THIS_MODULE"


def nested_dicts(depth: int, leaf: object) -> dict[str, object]:
    value: dict[str, object] = {"leaf": leaf}
    for level in range(depth):
        value = {f"level{level}": value}
    return value
