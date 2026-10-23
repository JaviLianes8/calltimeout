"""Process mode: how many pipe ends and sockets one call can carry, under each start method."""

from __future__ import annotations

import multiprocessing
import pickle
from collections.abc import Iterator
from multiprocessing.process import BaseProcess
from typing import Any

import _wire_targets
import pytest

from calltimeout import run

METHOD = multiprocessing.get_start_method()

# A forkserver start sends every descriptor of the call to the fork server in one message.
LIMIT = 248


@pytest.fixture
def starts(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[BaseProcess]]:
    started: list[BaseProcess] = []
    original = BaseProcess.start

    def spy(process: BaseProcess) -> None:
        started.append(process)
        original(process)

    monkeypatch.setattr(BaseProcess, "start", spy)
    yield started


@pytest.fixture
def ends() -> Iterator[list[Any]]:
    pairs = [multiprocessing.Pipe(duplex=False) for _ in range(300)]
    yield [writer for _, writer in pairs]
    for reader, writer in pairs:
        reader.close()
        writer.close()


@pytest.mark.skipif(METHOD == "forkserver", reason="a forkserver start passes fewer")
def test_hundreds_of_pipe_ends_in_one_call_reach_the_child(ends: list[Any]) -> None:
    assert run(_wire_targets.count, 120.0, args=tuple(ends), mode="process") == 300


@pytest.mark.skipif(METHOD != "forkserver", reason="only a forkserver start has the limit")
def test_a_forkserver_call_carries_up_to_the_limit_and_refuses_more_before_starting(
    ends: list[Any], starts: list[BaseProcess]
) -> None:
    assert run(_wire_targets.count, 120.0, args=tuple(ends[:LIMIT]), mode="process") == LIMIT
    starts.clear()
    for held in (ends[: LIMIT + 1], [multiprocessing.Lock(), *ends]):
        with pytest.raises(pickle.PicklingError, match=f"at most {LIMIT}") as info:
            run(_wire_targets.count, 120.0, args=tuple(held), mode="process")
        assert "descriptors" in str(info.value)
        assert starts == []
    assert run(_wire_targets.count, 30.0, args=(1, 2), mode="process") == 2


@pytest.mark.skipif(METHOD != "forkserver", reason="only a forkserver start has the limit")
def test_a_forkserver_call_counts_the_two_descriptors_of_each_queue() -> None:
    queues: list[Any] = [multiprocessing.SimpleQueue() for _ in range(LIMIT // 2 + 1)]
    with pytest.raises(pickle.PicklingError, match=f"at most {LIMIT}"):
        run(_wire_targets.count, 120.0, args=tuple(queues), mode="process")
    assert run(_wire_targets.count, 120.0, args=tuple(queues[:-1]), mode="process") == LIMIT // 2


@pytest.mark.skipif(METHOD != "forkserver", reason="only a forkserver start has the limit")
def test_a_forkserver_call_counts_the_one_descriptor_of_a_shared_value(
    ends: list[Any], starts: list[BaseProcess]
) -> None:
    value = multiprocessing.Value("i")
    held = (*ends[: LIMIT - 1], value)
    assert run(_wire_targets.count, 120.0, args=held, mode="process") == LIMIT
    starts.clear()
    with pytest.raises(pickle.PicklingError, match=f"holds {LIMIT + 1} descriptors"):
        run(_wire_targets.count, 120.0, args=(*ends[:LIMIT], value), mode="process")
    assert starts == []


@pytest.mark.skipif(METHOD != "forkserver", reason="only a forkserver start has the limit")
def test_a_forkserver_call_counts_no_descriptor_for_a_manager_proxy(ends: list[Any]) -> None:
    with multiprocessing.Manager() as manager:
        shared = manager.dict()
        held = (*ends[:LIMIT], shared)
        assert run(_wire_targets.count, 120.0, args=held, mode="process") == LIMIT + 1
