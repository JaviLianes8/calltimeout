"""Run a callable with a wall-clock timeout and get a typed result or a clean error.

- ``run`` calls a function under a time budget in a thread, a child process or under a
  SIGALRM timer; ``with_timeout`` does the same as a decorator that keeps the signature.
- ``CallTimeout`` (a ``TimeoutError``) is raised when the budget runs out, and
  ``CallCrashed`` (a ``RuntimeError``) when a process-mode child dies without a result.
- ``RemoteTraceback`` is the cause chained to an exception from a process-mode call: its
  text is the child's traceback.
- ``Mode`` is the ``Literal`` type of the three mechanism names, for annotating your
  own wrappers, so type checkers reject any other name.

>>> from calltimeout import run
>>> run(pow, 5.0, args=(2, 10))
1024

Mode
----
``Mode`` is ``Literal["thread", "process", "signal"]``, the names ``run`` and
``with_timeout`` accept. Use it to annotate your own wrappers:

>>> from typing import get_args
>>> from calltimeout import Mode, run
>>> def quick(mode: Mode) -> int:
...     return run(pow, 5.0, args=(2, 3), mode=mode)
>>> get_args(Mode)
('thread', 'process', 'signal')
>>> quick("thread")
8
"""

from ._api import Mode, run
from ._decorator import with_timeout
from ._errors import CallCrashed, CallTimeout, RemoteTraceback

__version__ = "1.0.0"

# The exceptions show and pickle as calltimeout.<Name>: tracebacks name the package and a
# pickle never depends on the private module that defines them.
CallCrashed.__module__ = __name__
CallTimeout.__module__ = __name__
RemoteTraceback.__module__ = __name__

__all__ = ["CallCrashed", "CallTimeout", "Mode", "RemoteTraceback", "run", "with_timeout"]
