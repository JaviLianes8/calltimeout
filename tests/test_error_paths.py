"""Process mode: calls that end in an error free their child at once and spoil no later call."""

from __future__ import annotations

import gc
import multiprocessing
import pickle
import threading
from collections.abc import Callable, Iterator
from multiprocessing.context import get_spawning_popen
from multiprocessing.process import BaseProcess
from multiprocessing.reduction import ForkingPickler

import _counting
import _targets
import _wire_targets
import pytest

from calltimeout import run

needs_pickling = pytest.mark.skipif(
    multiprocessing.get_start_method() == "fork", reason="fork pickles nothing"
)

SENT = "the call cannot be sent to the child process"


@pytest.fixture
def escaped(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[BaseException]]:
    """What escaped from Process.start(), which would leave a half-built start behind."""
    found: list[BaseException] = []
    original = BaseProcess.start

    def spy(process: BaseProcess) -> None:
        try:
            original(process)
        except BaseException as error:
            found.append(error)
            raise

    monkeypatch.setattr(BaseProcess, "start", spy)
    yield found


def _growth(call: Callable[[], None], times: int) -> int:
    """Handles left open by times calls while the cyclic collector does not run."""
    call()  # the first call may start helpers (a resource tracker, a fork server)
    gc.collect()
    gc.disable()
    try:
        before = _counting.handles()
        for _ in range(times):
            call()
        return _counting.handles() - before
    finally:
        gc.enable()
        gc.collect()


def _raising_call() -> None:
    with pytest.raises(ValueError):
        run(_targets.boom, 30.0, mode="process")


def _refused_call() -> None:
    once = _wire_targets.OnceThen(TypeError)
    with pytest.raises(pickle.PicklingError, match=SENT):
        run(_wire_targets.count, 30.0, args=(multiprocessing.Lock(), once), mode="process")


def test_calls_that_raise_leave_no_handle_open() -> None:
    assert _growth(_raising_call, 30) < 10


@needs_pickling
def test_calls_the_start_could_not_pickle_leave_no_handle_open() -> None:
    assert _growth(_refused_call, 20) < 10


def _delivers() -> bool:
    reader, writer = multiprocessing.Pipe(duplex=False)
    with reader:
        assert run(_wire_targets.write_and_close, 30.0, args=(writer,), mode="process") == "sent"
        writer.close()
        return reader.poll(5.0) and reader.recv() == "hello"


def _held_proxy(error: BaseException) -> tuple[object, ...]:
    return (_wire_targets.RefusingProxy(error),)


def _lock_and_once(error: BaseException) -> tuple[object, ...]:
    return (multiprocessing.Lock(), _wire_targets.OnceThen(error))


@needs_pickling
@pytest.mark.parametrize("holding", [_held_proxy, _lock_and_once], ids=["proxy", "lock"])
@pytest.mark.parametrize("make", [KeyboardInterrupt, SystemExit], ids=["interrupt", "exit"])
def test_a_base_exception_raised_while_the_start_pickles_is_raised_as_it_is(
    make: Callable[[], BaseException],
    holding: Callable[[BaseException], tuple[object, ...]],
    escaped: list[BaseException],
) -> None:
    error = make()
    with pytest.raises(type(error)) as info:
        run(_wire_targets.count, 30.0, args=holding(error), mode="process")
    assert info.value is error
    assert escaped == []  # the start finished; its child was stopped
    assert get_spawning_popen() is None
    assert all(_delivers() for _ in range(5))


@needs_pickling
@pytest.mark.parametrize("make", [TypeError, ValueError, pickle.PicklingError, RecursionError])
def test_an_error_raised_while_the_start_pickles_a_held_proxy_is_the_documented_one(
    make: Callable[[str], Exception], escaped: list[BaseException]
) -> None:
    with pytest.raises(pickle.PicklingError, match=SENT) as info:
        run(_wire_targets.count, 30.0, args=_held_proxy(make("refused")), mode="process")
    assert type(info.value.__cause__) is make
    assert escaped == []
    assert _delivers()


@needs_pickling
def test_a_call_that_fails_its_rehearsal_leaves_no_spawning_start_behind() -> None:
    with pytest.raises(pickle.PicklingError, match=SENT):
        run(
            _wire_targets.count,
            30.0,
            args=(multiprocessing.Lock(), threading.Lock()),
            mode="process",
        )
    assert get_spawning_popen() is None
    with pytest.raises(RuntimeError, match="inheritance"):
        ForkingPickler.dumps(multiprocessing.Lock())  # refused again outside a start
