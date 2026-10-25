"""Run a callable in a separate process that can be truly terminated."""

from __future__ import annotations

import multiprocessing
import time
from collections.abc import Callable, Mapping, Sequence
from multiprocessing.connection import Connection, wait
from multiprocessing.process import BaseProcess
from typing import Any, NoReturn, Protocol, TypeVar, cast

from ._errors import CallCrashed, Expired
from ._parcel import Parcel, prepickle
from ._thread import thread_name
from ._validate import reject_coroutine
from ._wire import pack_error, pack_result, unpack, unsendable

T = TypeVar("T")

# Seconds a terminated child gets to exit before it is killed (SIGTERM can be ignored).
GRACE = 1.0

# Longest sleep between checks that the child is still alive.
POLL = 0.25

# The target this child process was started for, so a decorated function knows it is
# already inside its own child and must not start another one.
_targets: list[object] = []


def claim_child_target(fn: object) -> bool:
    """Return True once if fn is the call this child process was started to run."""
    if _targets and _targets[-1] is fn:
        _targets.pop()
        return True
    return False


class _Reader(Protocol):
    def poll(self) -> bool: ...
    def recv_bytes(self) -> bytes: ...


def _child(parcel: Parcel) -> None:
    if parcel.conn is None:
        return  # the call could not be sent: the caller is stopping this child
    conn = cast(Connection, parcel.conn)
    try:
        try:
            # Loading can fail here (spawn and forkserver import fn by name): report it.
            fn, args, kwargs = parcel.open()
            _targets.append(fn)
            data = pack_result(reject_coroutine(fn(*args, **kwargs)))
        except BaseException as exc:
            data = pack_error(exc)
        conn.send_bytes(data)
    finally:
        conn.close()


def _await(reader: Any, process: BaseProcess, deadline: float) -> list[object]:
    """Wait for a result or the child's exit, whichever comes first; [] on overrun."""
    while True:
        left = deadline - time.monotonic()
        if left <= 0:
            return []
        ready = wait([reader, process.sentinel], min(left, POLL))
        if ready:
            return list(ready)
        if not process.is_alive():
            # A grandchild forked by the call inherits the pipe and, under fork and
            # spawn, the sentinel too, hiding the exit from both; waitpid still sees it.
            return [process.sentinel]


def _exits_within(process: BaseProcess, seconds: float) -> bool:
    # Not join(seconds): it waits on the sentinel, which a grandchild may hold open.
    deadline = time.monotonic() + seconds
    while process.is_alive() and time.monotonic() < deadline:
        time.sleep(0.01)
    return not process.is_alive()


def _stop(process: BaseProcess, *, finished: bool) -> None:
    """End the child: a finished one first gets to exit on its own.

    That lets its non-daemon threads finish, and its atexit handlers run where
    multiprocessing runs them in a child (spawn, and fork and forkserver from 3.13).
    """
    try:
        if not (finished and _exits_within(process, GRACE)) and process.is_alive():
            process.terminate()
            _exits_within(process, GRACE)
    finally:
        # Also reached on KeyboardInterrupt during the grace period.
        if process.is_alive():
            process.kill()
        process.join()
        # Releases its handles now: an error raised from the call can keep this process
        # object alive in a reference cycle until the next collection.
        process.close()


def _refuse(parcel: Parcel) -> NoReturn:
    """Raise what the start met pickling the call: the documented error, or the interrupt."""
    error, parcel.refused = parcel.refused, None
    try:
        if isinstance(error, Exception):
            error = unsendable(error)
            raise error from error.__cause__
        raise cast(BaseException, error)  # a KeyboardInterrupt, SystemExit, as it came
    finally:
        del error  # no cycle through this frame


def _receive(reader: _Reader, ready: Sequence[object]) -> bytes | None:
    # The child may have sent and exited in the same instant: check the pipe either way.
    if reader in ready or reader.poll():
        try:
            return reader.recv_bytes()
        except (EOFError, OSError):
            # Closed without a message, or cut short because the child died writing it.
            return None
    return None


def run_in_process(
    fn: Callable[..., T],
    timeout: float,
    args: tuple[object, ...],
    kwargs: Mapping[str, object],
) -> T:
    """Run fn in a child process, terminating it if it overruns the budget.

    Unlike thread mode this truly stops the work on timeout, but the result, and under
    spawn and forkserver fn and its arguments, must be picklable so they can cross the
    process boundary. A child that exits without a result raises CallCrashed as soon as
    it is gone. The budget covers pickling the call and starting the child; pickling runs
    here and is not interrupted, so only the check after it can stop the start.
    """
    deadline = time.monotonic() + timeout
    ctx = multiprocessing.get_context()
    data, held = prepickle(ctx.get_start_method(), (fn, args, dict(kwargs)))
    if time.monotonic() >= deadline:
        raise Expired  # pickling the call used up the budget: never start it
    reader, writer = ctx.Pipe(duplex=False)
    parcel = Parcel(writer, data, held)
    process = ctx.Process(target=_child, args=(parcel,), name=thread_name(fn))
    started = finished = False
    try:
        process.start()
        started = True
        writer.close()
        if parcel.refused is not None:
            _refuse(parcel)
        ready = _await(reader, process, deadline)
        if not ready:
            raise Expired
        data = _receive(reader, ready)
        if data is None:
            # No result will come: report the exit, but never wait past the deadline.
            if not _exits_within(process, deadline - time.monotonic()):
                raise Expired
            raise CallCrashed(process.exitcode)
        finished = True
    finally:
        # Runs on every exit, including KeyboardInterrupt while waiting.
        writer.close()
        reader.close()
        if started:
            _stop(process, finished=finished)
    return cast(T, unpack(data))
