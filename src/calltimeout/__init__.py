"""Run a callable with a wall-clock timeout and get a typed result or a clean error."""

from __future__ import annotations

from ._api import Mode, run
from ._decorator import with_timeout
from ._errors import CallCrashed, CallTimeout

__version__ = "0.2.0"

__all__ = ["CallCrashed", "CallTimeout", "Mode", "run", "with_timeout"]
