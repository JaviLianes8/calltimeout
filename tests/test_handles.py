"""Process mode: a pipe end or socket in a call never stays open in the caller."""

from __future__ import annotations

import gc
import multiprocessing
import pickle
import socket
from collections.abc import Callable, Iterator
from multiprocessing.connection import Client, Listener
from multiprocessing.process import BaseProcess
from typing import Any

import _counting
import _wire_targets
import pytest

from calltimeout import run

needs_pickling = pytest.mark.skipif(
    multiprocessing.get_start_method() == "fork", reason="fork pickles nothing"
)

SENT = "the call cannot be sent to the child process"


def _pipe() -> tuple[Any, Any]:
    reader, writer = multiprocessing.Pipe(duplex=False)
    return reader, writer


def _socket() -> tuple[Any, Any]:
    watched, sent = socket.socketpair()
    watched.settimeout(5.0)
    return watched, sent


def _socket_connection() -> tuple[Any, Any]:
    with Listener(("127.0.0.1", 0)) as listener:
        client = Client(listener.address)
        return listener.accept(), client


ENDS: dict[str, Callable[[], tuple[Any, Any]]] = {
    "pipe end": _pipe,
    "socket": _socket,
    "socket connection": _socket_connection,
}


def _ended(watched: Any) -> bool:
    """True once no copy of the other end is open anywhere."""
    try:
        if isinstance(watched, socket.socket):
            return watched.recv(16) == b""
        if not watched.poll(5.0):
            return False
        watched.recv()
    except TimeoutError:
        return False
    except (EOFError, OSError):
        return True  # Windows reports the end of a pipe or socket as an error
    return False


@pytest.fixture
def starts(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[BaseProcess]]:
    started: list[BaseProcess] = []
    original = BaseProcess.start

    def spy(process: BaseProcess) -> None:
        started.append(process)
        original(process)

    monkeypatch.setattr(BaseProcess, "start", spy)
    yield started


@needs_pickling
@pytest.mark.parametrize("kind", list(ENDS))
def test_an_end_in_a_call_whose_pickling_used_up_the_budget_is_not_left_open(
    kind: str, starts: list[BaseProcess]
) -> None:
    watched, sent = ENDS[kind]()
    slow = _wire_targets.Slow(0.3)
    result = run(_wire_targets.count, 0.1, args=(sent, slow), mode="process", default="late")
    assert result == "late"
    assert starts == []
    sent.close()
    assert _ended(watched)


@pytest.mark.parametrize("extra", [(), ("lock",)])
@pytest.mark.parametrize("kind", list(ENDS))
def test_an_end_in_a_call_stopped_before_its_child_loads_it_is_not_left_open(
    kind: str, extra: tuple[str, ...]
) -> None:
    others = [multiprocessing.Lock() for _ in extra]
    for _ in range(3):
        watched, sent = ENDS[kind]()
        run(_wire_targets.count, 0.02, args=(sent, *others), mode="process", default="late")
        sent.close()
        assert _ended(watched)
        watched.close()


def test_calls_stopped_before_their_child_loads_leave_no_handle_behind() -> None:
    def short_calls(times: int) -> int:
        for _ in range(times):
            run(_wire_targets.count, 0.02, args=(1,), mode="process", default="late")
        gc.collect()
        return _counting.handles()

    before = short_calls(3)
    assert short_calls(15) - before < 5


@pytest.mark.parametrize("extra", [(), ("lock",)])
def test_a_socket_sent_with_a_call_is_not_left_open_in_the_caller(extra: tuple[str, ...]) -> None:
    others = [multiprocessing.Lock() for _ in extra]
    watched, sent = _socket()
    assert run(_wire_targets.sock_send_and_close, 30.0, args=(sent, *others), mode="process")
    sent.close()
    assert watched.recv(16) == b"hi"
    assert _ended(watched)


@pytest.mark.parametrize("extra", [(), ("lock",)])
def test_a_socket_connection_sent_with_a_call_is_not_left_open_in_the_caller(
    extra: tuple[str, ...],
) -> None:
    others = [multiprocessing.Lock() for _ in extra]
    server, client = _socket_connection()
    result = run(_wire_targets.write_and_close, 30.0, args=(client, *others), mode="process")
    assert result == "sent"
    client.close()
    assert server.recv() == "hello"
    assert _ended(server)


CLOSED: dict[str, Callable[[], object]] = {
    "closed socket": lambda: _closed(socket.socket()),
    "closed pipe end": lambda: _closed(multiprocessing.Pipe()[0]),
}


def _closed(end: Any) -> object:
    end.close()
    return end


@needs_pickling
@pytest.mark.parametrize("extra", [(), ("lock",)])
@pytest.mark.parametrize("kind", list(CLOSED))
def test_a_closed_end_raises_pickling_error_and_spoils_no_later_call(
    kind: str, extra: tuple[str, ...], starts: list[BaseProcess]
) -> None:
    others = [multiprocessing.Lock() for _ in extra]
    with pytest.raises(pickle.PicklingError, match=SENT) as info:
        run(_wire_targets.count, 30.0, args=(CLOSED[kind](), *others), mode="process")
    assert "cannot send a closed" in str(info.value)
    assert type(info.value.__cause__) is ValueError  # cut in place, never the stand-in
    assert starts == []
    assert run(_wire_targets.count, 30.0, args=(1, 2), mode="process") == 2


@needs_pickling
def test_the_objects_beside_an_end_are_pickled_once_before_the_start(
    starts: list[BaseProcess],
) -> None:
    reader, writer = _pipe()
    once = _wire_targets.OnceThen(TypeError("this object pickles only once"))
    assert run(_wire_targets.write_and_close, 30.0, args=(writer, once), mode="process") == "sent"
    assert reader.recv() == "hello"
    never = _wire_targets.RaisesOnReduce(TypeError("never"))
    with pytest.raises(pickle.PicklingError, match=SENT):
        run(_wire_targets.write_and_close, 30.0, args=(writer, never), mode="process")
    assert len(starts) == 1
    assert run(_wire_targets.count, 30.0, args=(1, 2), mode="process") == 2
