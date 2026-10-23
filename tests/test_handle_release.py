"""Process mode: a call that ends in an error lets go of its child and its arguments at once.

Each test runs with the cyclic collector off: what a reference cycle holds would only be
freed by a collection, which a loop of failing calls may never reach before EMFILE.
"""

from __future__ import annotations

import contextlib
import gc
import multiprocessing
import pickle
import threading
from collections.abc import Iterator
from typing import Any

import _counting
import _targets
import _wire_targets
import pytest

from calltimeout import run

needs_pickling = pytest.mark.skipif(
    multiprocessing.get_start_method() == "fork", reason="fork pickles nothing"
)


@pytest.fixture
def no_collector() -> Iterator[None]:
    run(_targets.echo, 30.0, args=(1,), mode="process")  # helpers started once, before
    gc.collect()
    gc.disable()
    try:
        yield
    finally:
        gc.enable()
        gc.collect()


def _ended(reader: Any) -> bool:
    """True once no copy of the pipe's write end is open anywhere."""
    try:
        if reader.poll(5.0):
            reader.recv()
        return False
    except (EOFError, OSError):
        return True  # Windows reports the end of a pipe as an error
    finally:
        reader.close()


@pytest.mark.usefixtures("no_collector")
def test_the_errors_of_calls_that_raised_hold_no_handle_of_their_child() -> None:
    kept: list[BaseException] = []
    before = _counting.handles()
    for _ in range(20):
        try:
            run(_targets.boom, 30.0, mode="process")
        except ValueError as error:
            kept.append(error)
    assert len(kept) == 20
    assert _counting.handles() - before < 10


@pytest.mark.usefixtures("no_collector")
def test_an_end_sent_with_a_call_that_raised_is_closed_once_the_caller_drops_it() -> None:
    reader, writer = multiprocessing.Pipe(duplex=False)
    with contextlib.suppress(ValueError):
        run(_targets.boom_with, 30.0, args=(writer,), mode="process")
    del writer
    assert _ended(reader)


@needs_pickling
@pytest.mark.usefixtures("no_collector")
def test_an_end_sent_with_a_call_that_failed_its_rehearsal_is_closed_once_dropped() -> None:
    reader, writer = multiprocessing.Pipe(duplex=False)
    with contextlib.suppress(pickle.PicklingError):
        run(
            _wire_targets.count,
            30.0,
            args=(writer, multiprocessing.Lock(), threading.Lock()),
            mode="process",
        )
    del writer
    assert _ended(reader)
