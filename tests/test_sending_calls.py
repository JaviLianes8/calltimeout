"""Process mode: a call that cannot be pickled fails before any start and spoils nothing."""

from __future__ import annotations

import functools
import multiprocessing
import operator
import pickle
import threading
from collections.abc import Callable, Iterator
from multiprocessing.process import BaseProcess
from typing import Any, cast

import _targets
import _wire_targets
import pytest

from calltimeout import run, with_timeout

needs_pickling = pytest.mark.skipif(
    multiprocessing.get_start_method() == "fork", reason="fork pickles nothing"
)

SENT = "the call cannot be sent to the child process"

BAD_ARGUMENTS: dict[str, Callable[[], object]] = {
    "reduce raising RuntimeError": lambda: _wire_targets.RaisesOnReduce(RuntimeError("r" * 5000)),
    "reduce raising NotImplementedError": lambda: _wire_targets.RaisesOnReduce(
        NotImplementedError("n")
    ),
    "deeply nested": lambda: _wire_targets.nested(100_000),
    "thread lock": threading.Lock,
    "start-only lock then thread lock": lambda: (multiprocessing.Lock(), threading.Lock()),
    "start-only value guarded by a thread lock": lambda: multiprocessing.Value(
        "i", 0, lock=cast(Any, threading.Lock())
    ),
    "reduce raising RuntimeError like assert_spawning": _wire_targets.RefusesLikeAssertSpawning,
}


@pytest.fixture
def starts(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[BaseProcess]]:
    started: list[BaseProcess] = []
    original = BaseProcess.start

    def spy(process: BaseProcess) -> None:
        started.append(process)
        original(process)

    monkeypatch.setattr(BaseProcess, "start", spy)
    yield started


def _good_calls_still_work() -> None:
    # A start that failed half way once made the next children fail on Windows.
    assert [run(_targets.echo, 30.0, args=(n,), mode="process") for n in range(3)] == [0, 1, 2]


@needs_pickling
@pytest.mark.parametrize("make", list(BAD_ARGUMENTS.values()), ids=list(BAD_ARGUMENTS))
def test_an_argument_that_cannot_pickle_raises_pickling_error_and_starts_nothing(
    make: Callable[[], object], starts: list[BaseProcess]
) -> None:
    bad = make()
    for _ in range(2):
        with pytest.raises(pickle.PicklingError, match=SENT) as info:
            run(_targets.echo, 30.0, args=(bad,), mode="process")
        assert starts == []
        assert isinstance(info.value.__cause__, Exception)  # pickle's own error, chained
        assert len(str(info.value)) <= 400
        _good_calls_still_work()
        starts.clear()


@needs_pickling
def test_a_pool_argument_raises_pickling_error_and_spoils_no_later_call() -> None:
    pool = multiprocessing.Pool(1)
    try:
        for _ in range(3):
            with pytest.raises(pickle.PicklingError, match=SENT):
                run(_targets.echo, 30.0, args=(pool,), mode="process")
            with pytest.raises(pickle.PicklingError, match=SENT):
                run(_targets.echo, 30.0, args=((multiprocessing.Lock(), pool),), mode="process")
            _good_calls_still_work()
    finally:
        pool.terminate()
        pool.join()


@needs_pickling
def test_an_unpicklable_function_raises_the_same_error_on_every_python() -> None:
    with pytest.raises(pickle.PicklingError, match=SENT):
        run(lambda: 1, 30.0, mode="process")


@needs_pickling
def test_pickles_notes_quoting_a_huge_key_are_bounded() -> None:
    secret = "TOPSECRET" + "z" * 100_000
    with pytest.raises(pickle.PicklingError) as info:
        run(_targets.echo, 30.0, args=({secret: threading.Lock()},), mode="process")
    assert "TOPSECRET" not in str(info.value)
    notes = getattr(info.value.__cause__, "__notes__", [])
    assert len(notes) <= 11
    assert all(len(note) <= 63 for note in notes), notes


def test_start_only_objects_still_reach_the_child() -> None:
    queue: multiprocessing.Queue[str] = multiprocessing.Queue()
    lock = multiprocessing.Lock()
    assert run(_targets.put_in_queue, 30.0, args=(queue, lock), mode="process") == "put"
    assert queue.get(timeout=10) == "sent"


@pytest.mark.parametrize(
    ("fn", "argument", "expected"),
    [
        (functools.partial(operator.mul, 2), 21, 42),
        (_wire_targets.Multiply(3), 5, 15),
    ],
)
def test_the_decorator_sends_a_callable_that_pickles_by_value(
    fn: Callable[[int], int], argument: int, expected: int
) -> None:
    assert run(fn, 30.0, args=(argument,), mode="process") == expected
    assert with_timeout(30.0, mode="process")(fn)(argument) == expected


def test_the_child_process_is_named_after_the_call() -> None:
    assert run(_wire_targets.process_name, 30.0, mode="process") == "calltimeout:process_name"


def test_a_proxy_of_a_manager_with_its_own_authkey_reaches_the_child() -> None:
    from multiprocessing.managers import SyncManager

    with SyncManager(authkey=b"its-own-key") as manager:
        shared = manager.dict(a=1, b=2)
        assert run(_wire_targets.size, 60.0, args=(shared,), mode="process") == 2
        lock = multiprocessing.Lock()
        assert run(_wire_targets.size, 60.0, args=(shared, lock), mode="process") == 2


def test_an_argument_whose_class_attribute_raises_is_sent_as_it_pickles() -> None:
    assert run(_wire_targets.count, 30.0, args=(_wire_targets.OddClass(),), mode="process") == 1


def test_each_end_socket_and_proxy_in_one_call_reaches_its_own_peer() -> None:
    import socket
    from multiprocessing.managers import SyncManager

    first_reader, first = multiprocessing.Pipe(duplex=False)
    second_reader, second = multiprocessing.Pipe(duplex=False)
    watched, sock = socket.socketpair()
    watched.settimeout(10.0)
    with SyncManager() as manager, watched, sock:
        shared = manager.list()
        args = (first, second, sock, shared)
        assert run(_wire_targets.deliver_each, 60.0, args=args, mode="process") == "sent"
        assert first_reader.poll(10.0) and first_reader.recv() == "first"
        assert second_reader.poll(10.0) and second_reader.recv() == "second"
        assert watched.recv(16) == b"sock"
        assert list(shared) == ["shared"]
