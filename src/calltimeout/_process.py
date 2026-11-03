"""Run a callable in a separate process that can be truly terminated."""

from __future__ import annotations

import multiprocessing
import threading
import time
from collections.abc import Callable, Mapping, Sequence
from multiprocessing.connection import wait
from multiprocessing.process import BaseProcess
from typing import Any, NoReturn, Protocol, TypeVar, cast

from ._child import serve
from ._errors import CallCrashed, Expired
from ._parcel import Parcel, prepickle
from ._thread import thread_name
from ._wire import unpack, unsendable

T = TypeVar("T")

# Seconds a terminated child gets to exit before it is killed (SIGTERM can be ignored).
GRACE = 1.0

# Longest sleep between checks that the child is still alive.
POLL = 0.25


class _Reader(Protocol):
    def poll(self) -> bool: ...
    def recv_bytes(self) -> bytes: ...


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


def _watch(process: BaseProcess, deadline: float, done: threading.Event, late: list[bool]) -> None:
    """Stop the child at the deadline unless done: terminated, then killed after GRACE."""
    if done.wait(max(deadline - time.monotonic(), 0.0)):
        return
    late.append(True)
    process.terminate()
    if not done.wait(GRACE):
        process.kill()  # also ends a stopped child, which SIGTERM does not


def _receive(
    reader: _Reader, ready: Sequence[object], process: BaseProcess, deadline: float
) -> bytes | None:
    """The child's message, or None if it closed the pipe or died without sending one.

    The deadline holds while the message arrives: on POSIX a long one is written in two
    parts, and a child stalled between or during them would block the read for good. It
    is stopped at the deadline instead, and the call then ran out of time.
    """
    # The child may have sent and exited in the same instant: check the pipe either way.
    if not (reader in ready or reader.poll()):
        return None
    done = threading.Event()
    late: list[bool] = []
    watchdog = threading.Thread(target=_watch, args=(process, deadline, done, late), daemon=True)
    watchdog.start()
    try:
        return reader.recv_bytes()
    except (EOFError, OSError):
        # Closed without a message, or cut short because the child died writing it.
        if late:
            raise Expired from None
        return None
    finally:
        done.set()
        watchdog.join()  # before the child is reaped: it must never signal a reused pid


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
    it is gone. The budget covers pickling the call, starting the child and receiving the
    result; pickling runs here and is not interrupted, so only the check after it can stop
    the start. The result is rebuilt here too, once it has arrived: outside the budget, not
    interrupted.
    """
    deadline = time.monotonic() + timeout
    ctx = multiprocessing.get_context()
    data, held = prepickle(ctx.get_start_method(), (fn, args, dict(kwargs)))
    if time.monotonic() >= deadline:
        raise Expired  # pickling the call used up the budget: never start it
    reader, writer = ctx.Pipe(duplex=False)
    parcel = Parcel(writer, data, held)
    process = ctx.Process(target=serve, args=(parcel,), name=thread_name(fn))
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
        data = _receive(reader, ready, process, deadline)
        if data is None:
            # No result will come: report the exit, but never wait past the deadline.
            if not _exits_within(process, deadline - time.monotonic()):
                raise Expired
            raise CallCrashed(cast(int, process.exitcode))  # it exited, so it has a code
        finished = True
    finally:
        # Runs on every exit, including KeyboardInterrupt while waiting.
        writer.close()
        reader.close()
        if started:
            _stop(process, finished=finished)
    return cast(T, unpack(data))
