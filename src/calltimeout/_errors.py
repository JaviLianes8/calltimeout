"""Exceptions raised when a call overruns its budget or its process dies."""

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

    def __init__(self, exitcode: int | None) -> None:
        self.exitcode = exitcode
        super().__init__(f"the call's process exited with code {shown(exitcode)} before returning")

    def __reduce__(self) -> tuple[type[CallCrashed], tuple[int | None], dict[str, Any]]:
        return (type(self), (self.exitcode,), dict(vars(self)))


class Expired(Exception):
    """Private signal from a runner to the entry point: this call's own budget ran out."""
