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


class QualMeta(type):
    """Its classes refuse to give their qualified name (doctest still reads their module)."""

    def __getattribute__(cls, name: str) -> object:
        if name == "__qualname__":
            raise RuntimeError(f"{name} refused")
        return super().__getattribute__(name)


class QualErr(Exception, metaclass=QualMeta):
    """Its type cannot be named, and its text is long."""

    def __str__(self) -> str:
        return "SECRET-" + "Q" * 100_000


class LyingStr(str):
    """Claims to be empty, whatever it holds."""

    def __len__(self) -> int:
        return 0


class LyingErr(Exception):
    """Its long text claims to be short."""

    def __str__(self) -> str:
        return LyingStr("SECRET-" + "Y" * 100_000)


class Flip(Exception):
    """Its text is short every other time it is read, long the rest."""

    reads = 0

    def __str__(self) -> str:
        Flip.reads += 1
        return "short" if Flip.reads % 2 else "SECRET-" + "F" * 100_000


class FlipArg:
    """An argument of an error whose text is short only the first time."""

    def __init__(self) -> None:
        self.reads = 0

    def __str__(self) -> str:
        self.reads += 1
        return "short" if self.reads == 1 else "SECRET-" + "A" * 100_000


def with_notes(notes: object) -> Exception:
    """A TypeError whose notes were set to something other than a list of str."""
    error = TypeError("plain")
    error.__notes__ = notes  # type: ignore[attr-defined]
    return error


def chained_to(huge: BaseException) -> Exception:
    """A short TypeError raised while handling, and from, a huge error."""
    try:
        raise huge
    except BaseException:
        try:
            raise TypeError("not registered") from huge
        except TypeError as error:
            return error


def in_context_of(huge: BaseException) -> Exception:
    """A short TypeError raised while handling a huge error, as a failed lookup does."""
    try:
        raise huge
    except BaseException:
        try:
            raise TypeError("not registered")
        except TypeError as error:
            return error


class FlipStr(str):
    """A str subclass whose own str is short only the first time it is read."""

    def __str__(self) -> str:
        self.reads = getattr(self, "reads", 0) + 1
        return "short" if self.reads == 1 else "SECRET-" + "B" * 100_000


class FlipRepr:
    """An argument whose repr is short only the first time it is read."""

    def __init__(self) -> None:
        self.reads = 0

    def __repr__(self) -> str:
        self.reads += 1
        return "short" if self.reads == 1 else "SECRET-" + "C" * 100_000


class LyingText:
    """An argument whose str is a long str subclass that claims to be empty."""

    def __str__(self) -> str:
        return LyingStr("SECRET-" + "D" * 100_000)


class BadStrArg:
    """An argument whose str raises."""

    def __str__(self) -> str:
        raise ValueError("__str__ of this argument fails")


class NoteList(list[object]):
    """A list subclass, which traceback prints as notes but is not a plain list."""


class RaisingModule(type):
    """Its classes raise when asked for their module, which traceback and pickle both read."""

    def __getattribute__(cls, name: str) -> object:
        if name == "__module__":
            raise ZeroDivisionError(f"{name} refused")
        return super().__getattribute__(name)


_made: dict[str, type[Exception]] = {}


def module_err() -> type[Exception]:
    """An error type whose tracebacks cannot be formatted and which cannot be pickled.

    Made on demand: collectors read the module of every class defined at module level.
    """
    if not _made:

        class ModuleErr(Exception, metaclass=RaisingModule):
            pass

        _made["ModuleErr"] = ModuleErr
    return _made["ModuleErr"]


def raise_module_err() -> None:
    raise module_err()("boom")


class LyingUnpicklable(Exception):
    """Cannot be rebuilt (it takes two arguments), and its long text claims to be empty."""

    def __init__(self, first: str, second: str) -> None:
        super().__init__(first)

    def __str__(self) -> str:
        return LyingStr("SECRET-" + "U" * 100_000)


def raise_lying_unpicklable() -> None:
    raise LyingUnpicklable("x", "y")
