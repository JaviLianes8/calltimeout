"""What a process-mode child runs: load the call, run it, send back its outcome."""

from __future__ import annotations

from multiprocessing.connection import Connection
from typing import cast

from ._parcel import Parcel
from ._validate import reject_coroutine
from ._wire import pack_error, pack_result, unloadable

# The target this child process was started for, so a decorated function knows it is
# already inside its own child and must not start another one.
_targets: list[object] = []


def claim_child_target(fn: object) -> bool:
    """Return True once if fn is the call this child process was started to run."""
    if _targets and _targets[-1] is fn:
        _targets.pop()
        return True
    return False


def _outcome(parcel: Parcel) -> bytes:
    """The call's result or error, pickled as the caller unpacks it."""
    try:
        try:
            # Spawn and forkserver import fn by name here, and rebuild every argument.
            fn, args, kwargs = parcel.open()
        except Exception as problem:
            error = unloadable(problem)
        else:
            _targets.append(fn)
            return pack_result(reject_coroutine(fn(*args, **kwargs)))
        raise error from error.__cause__  # outside that handler: no unbounded context
    except BaseException as exc:
        return pack_error(exc)


def serve(parcel: Parcel) -> None:
    """The child process's target: run the call and send its outcome down the pipe."""
    if parcel.conn is None:
        return  # the call could not be sent: the caller is stopping this child
    conn = cast(Connection, parcel.conn)
    try:
        conn.send_bytes(_outcome(parcel))
    finally:
        conn.close()
