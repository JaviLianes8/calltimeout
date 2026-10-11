"""Run a callable with a wall-clock timeout and get a typed result or a clean error."""

from __future__ import annotations

from ._api import Mode, run
from ._errors import CallTimeout

__version__ = "0.1.0"

__all__ = ["CallTimeout", "Mode", "run"]
