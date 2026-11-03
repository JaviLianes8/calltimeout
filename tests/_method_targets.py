"""Decorated methods of every kind, at module level so spawn and forkserver children find them."""

from __future__ import annotations

import os

from calltimeout import with_timeout


class Box:
    @with_timeout(30.0, mode="process")
    def method(self, value: int) -> tuple[str, int, int]:
        return (type(self).__name__, value, os.getpid())

    @staticmethod
    @with_timeout(30.0, mode="process")
    def static(value: int) -> tuple[int, int]:
        return (value, os.getpid())

    @classmethod
    @with_timeout(30.0, mode="process")
    def klass(cls, value: int) -> tuple[str, int, int]:
        return (cls.__name__, value, os.getpid())


class Sub(Box):
    pass
