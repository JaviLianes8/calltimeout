"""Exception raised when a call exceeds its wall-clock budget."""

from __future__ import annotations


class CallTimeout(TimeoutError):
    """Raised when a call does not finish within its allotted time."""

    def __init__(self, timeout: float) -> None:
        self.timeout = timeout
        super().__init__(f"call did not finish within {timeout} seconds")
