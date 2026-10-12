"""Optional start method override, to run the process tests under each one."""

from __future__ import annotations

import multiprocessing
import os

_method = os.environ.get("CALLTIMEOUT_START_METHOD")
if _method:
    multiprocessing.set_start_method(_method, force=True)
