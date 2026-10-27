"""Targets whose outcome is odd on its way back from the child, at module level for spawn."""

from __future__ import annotations

import multiprocessing
import os
import sys
import time
import types
from typing import Any

from calltimeout import with_timeout


@with_timeout(30.0, mode="process")
def inner_pid() -> int:
    return os.getpid()


def outer() -> tuple[int, int]:
    return os.getpid(), inner_pid()


@with_timeout(0.5, mode="process")
def inner_slow() -> str:
    time.sleep(5.0)
    return "finished"


def outer_slow() -> str:
    try:
        return inner_slow()
    except Exception as exc:
        return type(exc).__name__


class Owner:
    @classmethod
    @with_timeout(30.0, mode="process")
    def name(cls) -> str:
        return multiprocessing.current_process().name


class Refusing(type):
    @property
    def __name__(cls) -> str:  # type: ignore[override]
        raise RuntimeError("__name__ refused")


class Unpicklable(Exception, metaclass=Refusing):
    def __reduce__(self) -> Any:
        raise TypeError("no pickling")


def raise_unpicklable() -> None:
    raise Unpicklable("boom")


class RebuiltAsText(Exception):
    def __reduce__(self) -> Any:
        return (str, ("rebuilt as a str",))


class RebuiltAsObject(Exception):
    def __reduce__(self) -> Any:
        return (types.SimpleNamespace, ())


def raise_rebuilt_as_text() -> None:
    raise RebuiltAsText("the real error")


def raise_rebuilt_as_object() -> None:
    raise RebuiltAsObject("the real error")


def _refuse_to_load(size: int) -> object:
    raise KeyError("k" * size)


class LoadsBadly:
    """Pickles fine in the caller; rebuilding it in the child raises a huge KeyError."""

    def __init__(self, size: int) -> None:
        self.size = size

    def __reduce__(self) -> Any:
        return (_refuse_to_load, (self.size,))


def stall_after_header() -> bytes:
    """Return 1 MB, but stall once the length header is written (POSIX writes it apart)."""
    writes = [0]

    def hook(frame: object, event: str, arg: Any) -> None:
        if event == "c_return" and getattr(arg, "__name__", "") == "write":
            writes[0] += 1
            if writes[0] == 1:
                sys.setprofile(None)
                time.sleep(30.0)

    sys.setprofile(hook)
    return b"x" * 1_000_000
