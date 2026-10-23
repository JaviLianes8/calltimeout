"""Exceptions an argument's reduce may raise that resist being shortened."""

from __future__ import annotations


class ReadOnlyArgs(Exception):
    """Its args cannot be set and its text is long."""

    @property
    def args(self) -> tuple[object, ...]:  # type: ignore[override]
        return ("x",)

    def __str__(self) -> str:
        return "R" * 1000


class LongText(Exception):
    """Its text comes from __str__, not from args."""

    def __str__(self) -> str:
        return "SECRET-" + "L" * 100_000


class BadStr(Exception):
    """Its __str__ raises."""

    def __str__(self) -> str:
        raise ValueError("__str__ of this error fails")
