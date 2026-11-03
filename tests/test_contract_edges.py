"""Contracts added after the mutation round: timing, snapshots and per-call children."""

from __future__ import annotations

import multiprocessing
import os
import sys
import threading
import time
from collections.abc import Iterator, Mapping
from multiprocessing.process import BaseProcess
from pathlib import Path

import _targets
import pytest

from calltimeout import CallTimeout, Mode, run

MODES: list[Mode] = ["thread", "process"]
if sys.platform != "win32":
    MODES.append("signal")


@pytest.mark.parametrize("mode", MODES)
def test_an_overrun_ends_after_the_budget_and_well_before_twice_it(mode: Mode) -> None:
    release = threading.Event()
    target = release.wait if mode == "thread" else _targets.slow
    started = time.monotonic()
    with pytest.raises(CallTimeout):
        run(target, 1.0, args=(30.0,), mode=mode)
    elapsed = time.monotonic() - started
    release.set()
    assert 1.0 <= elapsed < (2.5 if mode == "process" else 1.6), elapsed


class _ReadWhere(Mapping[str, str]):
    """A mapping whose value says which thread read it."""

    def __getitem__(self, key: str) -> str:
        return threading.current_thread().name

    def __iter__(self) -> Iterator[str]:
        return iter(["value"])

    def __len__(self) -> int:
        return 1


@pytest.mark.parametrize("mode", MODES)
def test_kwargs_are_read_once_in_the_caller_before_the_call_starts(mode: Mode) -> None:
    caller = threading.current_thread().name
    assert run(_targets.echo, 30.0, kwargs=_ReadWhere(), mode=mode) == caller


class _IterHidesKeys(dict):  # type: ignore[type-arg]
    """Iteration shows only the str keys; keys() and the storage hold them all."""

    def __iter__(self) -> Iterator[object]:
        return iter([key for key in dict.keys(self) if isinstance(key, str)])


class _ChangesKeys(Mapping[object, int]):
    """Its first iteration shows only str keys, every later one adds an int key."""

    def __init__(self) -> None:
        self.passes = 0

    def __getitem__(self, key: object) -> int:
        return 1

    def __iter__(self) -> Iterator[object]:
        self.passes += 1
        return iter(["a"] if self.passes == 1 else ["a", 7])

    def __len__(self) -> int:
        return 1


@pytest.mark.parametrize("mode", MODES)
def test_the_kwargs_checked_are_the_kwargs_the_call_gets(
    mode: Mode, monkeypatch: pytest.MonkeyPatch
) -> None:
    started: list[BaseProcess] = []
    original = BaseProcess.start

    def spy(process: BaseProcess) -> None:
        started.append(process)
        original(process)

    monkeypatch.setattr(BaseProcess, "start", spy)
    hiding = _IterHidesKeys({"a": 1, 7: 2})
    with pytest.raises(TypeError) as info:
        run(_targets.keywords, 30.0, kwargs=hiding, mode=mode)
    assert str(info.value) == "kwargs keys must be strings"
    assert info.value.__cause__ is None
    assert started == []
    monkeypatch.undo()
    changing = _ChangesKeys()
    assert run(_targets.keywords, 30.0, kwargs=changing, mode=mode) == {"a": 1}  # type: ignore[arg-type]
    assert changing.passes == 1


def test_a_call_whose_pickling_spends_the_budget_starts_no_process(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    if multiprocessing.get_start_method() == "fork":
        pytest.skip("fork pickles nothing")
    started: list[BaseProcess] = []
    original = BaseProcess.start

    def spy(process: BaseProcess) -> None:
        started.append(process)
        original(process)

    monkeypatch.setattr(BaseProcess, "start", spy)
    with pytest.raises(CallTimeout):
        run(
            _targets.touch_with,
            0.3,
            args=(str(tmp_path / "m"), _targets.SlowToPickle()),
            mode="process",
        )
    assert started == []


def test_a_decorated_process_function_called_inside_its_own_child_gets_a_new_child() -> None:
    pids = _targets.nested_pids(2)
    assert len(pids) == 3
    assert len({os.getpid(), *pids}) == 4
