"""Exceptions raised when a call overruns its budget or its process dies."""

from __future__ import annotations


class CallTimeout(TimeoutError):
    """Raised when a call does not finish within its allotted time."""

    def __init__(self, timeout: float) -> None:
        self.timeout = timeout
        super().__init__(f"call did not finish within {timeout} seconds")

    def __reduce__(self) -> tuple[type[CallTimeout], tuple[float]]:
        # The default reduce would rebuild from the message and lose the number.
        return (type(self), (self.timeout,))


class CallCrashed(RuntimeError):
    """Raised in process mode when the child exits without sending a result."""

    def __init__(self, exitcode: int | None) -> None:
        self.exitcode = exitcode
        super().__init__(f"the call's process exited with code {exitcode} before returning")

    def __reduce__(self) -> tuple[type[CallCrashed], tuple[int | None]]:
        return (type(self), (self.exitcode,))


class Expired(Exception):
    """Private signal from a runner to the entry point: this call's own budget ran out."""
