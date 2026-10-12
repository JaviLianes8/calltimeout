"""Run a callable in a separate process that can be truly terminated."""

from __future__ import annotations

import multiprocessing
import pickle
import time
import traceback
from collections.abc import Callable, Mapping, Sequence
from multiprocessing.connection import Connection, wait
from multiprocessing.process import BaseProcess
from multiprocessing.reduction import ForkingPickler
from typing import Any, Protocol, TypeVar, cast

from ._errors import CallCrashed, Expired
from ._thread import thread_name
from ._validate import reject_coroutine

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


class RemoteTraceback(Exception):
    """Carries the child's formatted traceback as the cause of a re-raised error."""

    def __init__(self, text: str) -> None:
        super().__init__(text)
        self.text = text

    def __str__(self) -> str:
        return self.text


def _pack_error(exc: BaseException) -> bytes:
    text = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    try:
        data = pickle.dumps((False, exc, text))
        pickle.loads(data)  # an exception can pickle and still fail to rebuild
    except Exception as problem:
        name = f"{type(exc).__module__}.{type(exc).__qualname__}"
        stand_in = RuntimeError(f"{name}: {exc} (not picklable: {problem!r})")
        data = pickle.dumps((False, stand_in, text))
    return data


def _child(conn: Connection, call: object) -> None:
    if isinstance(call, bytes):
        call = pickle.loads(call)
    fn, args, kwargs = cast(
        tuple[Callable[..., object], tuple[object, ...], dict[str, object]], call
    )
    _targets.append(fn)
    try:
        try:
            value = reject_coroutine(fn(*args, **kwargs))
        except BaseException as exc:
            data = _pack_error(exc)
        else:
            try:
                data = pickle.dumps((True, value, ""))
            except Exception as problem:
                error = pickle.PicklingError(f"the call's result cannot be sent back: {problem!r}")
                data = _pack_error(error)
        conn.send_bytes(data)
    finally:
        conn.close()


def _await(reader: Any, process: BaseProcess, timeout: float) -> list[object]:
    """Wait for a result or the child's exit, whichever comes first; [] on overrun."""
    deadline = time.monotonic() + timeout
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


def _stop(process: BaseProcess) -> None:
    if process.is_alive():
        process.terminate()
        # Not join(GRACE): it waits on the sentinel, which a grandchild may hold open.
        deadline = time.monotonic() + GRACE
        while process.is_alive() and time.monotonic() < deadline:
            time.sleep(0.01)
        if process.is_alive():
            process.kill()
    process.join()


def _receive(reader: _Reader, ready: Sequence[object]) -> bytes | None:
    # The child may have sent and exited in the same instant: check the pipe either way.
    if reader in ready or reader.poll():
        try:
            return reader.recv_bytes()
        except EOFError:
            return None
    return None


def run_in_process(
    fn: Callable[..., T],
    timeout: float,
    args: tuple[object, ...],
    kwargs: Mapping[str, object],
) -> T:
    """Run fn in a child process, terminating it if it overruns the budget.

    Unlike thread mode this truly stops the work on timeout, but fn, its arguments
    and its result must be picklable so they can cross the process boundary. A child
    that exits without a result raises CallCrashed as soon as it is gone.
    """
    ctx = multiprocessing.get_context()
    call: object = (fn, args, dict(kwargs))
    if ctx.get_start_method() != "fork":
        # Pickle up front: a start that fails half way through pickling can leave the
        # next child of this process writing to a stale pipe handle (seen on Windows).
        call = bytes(ForkingPickler.dumps(call))
    reader, writer = ctx.Pipe(duplex=False)
    process = ctx.Process(target=_child, args=(writer, call), name=thread_name(fn))
    started = False
    try:
        process.start()
        started = True
        writer.close()
        ready = _await(reader, process, timeout)
        if not ready:
            raise Expired
        data = _receive(reader, ready)
        if data is None:
            process.join()
            raise CallCrashed(process.exitcode)
    finally:
        # Runs on every exit, including KeyboardInterrupt while waiting.
        writer.close()
        reader.close()
        if started:
            _stop(process)
    ok, payload, text = pickle.loads(data)
    if ok:
        return cast(T, payload)
    error = cast(BaseException, payload)
    error.__cause__ = RemoteTraceback(text)
    raise error
