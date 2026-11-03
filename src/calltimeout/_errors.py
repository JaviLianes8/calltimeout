"""Exceptions for a call that overruns its budget or whose child dies, and its traceback."""

from __future__ import annotations

from typing import Any

from ._text import shown


class CallTimeout(TimeoutError):
    """Raised when a call does not finish within its budget.

    ``timeout`` is the budget in seconds. As a ``TimeoutError`` it is caught by existing
    ``except TimeoutError`` clauses, and it keeps ``timeout`` (and any notes) through
    pickle and copy, so it can cross a process boundary.

    >>> from calltimeout import CallTimeout
    >>> error = CallTimeout(0.5)
    >>> error.timeout
    0.5
    >>> str(error)
    'call did not finish within 0.5 seconds'
    >>> isinstance(error, TimeoutError)
    True
    """

    def __init__(self, timeout: float) -> None:
        self.timeout = timeout
        super().__init__(f"call did not finish within {shown(timeout)} seconds")

    def __reduce__(self) -> tuple[type[CallTimeout], tuple[float], dict[str, Any]]:
        # The default reduce would rebuild from the message and lose the number.
        return (type(self), (self.timeout,), dict(vars(self)))


class CallCrashed(RuntimeError):
    """Raised in process mode when the child process exits without sending a result.

    ``exitcode`` is the child's exit code as ``multiprocessing`` reports it: the code
    given to ``os._exit``, or ``-N`` for a child killed by signal ``N`` on POSIX (the
    out-of-memory killer's SIGKILL gives ``-9``).

    >>> from calltimeout import CallCrashed
    >>> error = CallCrashed(3)
    >>> error.exitcode
    3
    >>> str(error)
    "the call's process exited with code 3 before returning"
    """

    def __init__(self, exitcode: int) -> None:
        self.exitcode = exitcode
        super().__init__(f"the call's process exited with code {shown(exitcode)} before returning")

    def __reduce__(self) -> tuple[type[CallCrashed], tuple[int], dict[str, Any]]:
        return (type(self), (self.exitcode,), dict(vars(self)))


class RemoteTraceback(Exception):
    """The cause chained to an exception raised by a process-mode call in its child.

    ``text`` is the child's formatted traceback, also the exception's text, so a printed
    traceback shows where the call failed in the child.

    >>> from calltimeout import RemoteTraceback, run
    >>> try:
    ...     run(int, 30.0, args=("ten",), mode="process")
    ... except ValueError as error:
    ...     cause = error.__cause__
    >>> isinstance(cause, RemoteTraceback)
    True
    >>> cause.text.startswith("Traceback (most recent call last):")
    True
    >>> cause.text.splitlines()[-1]
    "ValueError: invalid literal for int() with base 10: 'ten'"
    """

    def __init__(self, text: str) -> None:
        # Built with something other than text, it still shows (bounded) instead of failing.
        super().__init__(text if isinstance(text, str) else shown(text))
        self.text = text

    def __str__(self) -> str:
        return self.text if isinstance(self.text, str) else shown(self.text)


class Expired(Exception):
    """Private signal from a runner to the entry point: this call's own budget ran out."""
