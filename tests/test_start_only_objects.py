"""Process mode: locks, queues and pipes in a call, however many, cost one rehearsal."""

from __future__ import annotations

import multiprocessing
import os
import pickle
import re
import threading
from collections.abc import Callable

import _targets
import _wire_targets
import pytest

from calltimeout import run

needs_pickling = pytest.mark.skipif(
    multiprocessing.get_start_method() == "fork", reason="fork pickles nothing"
)

SENT = "the call cannot be sent to the child process"

MANY: dict[str, Callable[[], tuple[object, ...]]] = {
    "150 locks": lambda: tuple(multiprocessing.Lock() for _ in range(150)),
    "60 events": lambda: tuple(multiprocessing.Event() for _ in range(60)),
    "120 values": lambda: tuple(multiprocessing.Value("i", 0) for _ in range(120)),
}


@pytest.mark.parametrize("make", list(MANY.values()), ids=list(MANY))
def test_any_number_of_start_only_objects_reach_the_child(
    make: Callable[[], tuple[object, ...]],
) -> None:
    objects = make()
    assert run(_wire_targets.count, 120.0, args=objects, mode="process") == len(objects)


@needs_pickling
def test_the_call_is_pickled_a_fixed_number_of_times_whatever_it_holds() -> None:
    # One trial, one rehearsal and the start itself: never once per lock.
    locks = [multiprocessing.Lock() for _ in range(50)]
    _wire_targets.REDUCED.clear()
    assert run(_wire_targets.count, 60.0, args=(_wire_targets.Counted(), locks), mode="process")
    assert len(_wire_targets.REDUCED) <= 3
    _wire_targets.REDUCED.clear()
    assert run(_wire_targets.count, 60.0, args=(_wire_targets.Counted(),), mode="process")
    assert len(_wire_targets.REDUCED) == 1


def _open_fds() -> int:
    return len(os.listdir("/proc/self/fd")) if os.path.isdir("/proc/self/fd") else 0


@pytest.mark.parametrize("extra", [(), ("lock",), ("lock", "queue")])
def test_a_pipe_end_sent_with_a_call_is_not_left_open_in_the_caller(
    extra: tuple[str, ...],
) -> None:
    makers: dict[str, Callable[[], object]] = {
        "lock": multiprocessing.Lock,
        "queue": multiprocessing.Queue,
    }
    others = [makers[name]() for name in extra]
    counts = []
    for _ in range(4):
        reader, writer = multiprocessing.Pipe(duplex=False)
        result = run(_wire_targets.write_and_close, 30.0, args=(writer, *others), mode="process")
        assert result == "sent"
        writer.close()
        assert reader.recv() == "hello"
        # A duplicate of the writer left open in this process would hide the end of file.
        try:
            ended = reader.poll(10.0)
        except BrokenPipeError:
            ended = True  # how Windows reports the end of the pipe to poll()
        assert ended
        with pytest.raises((EOFError, OSError)):
            reader.recv()
        reader.close()
        counts.append(_open_fds())
    assert counts[-1] <= counts[1], counts  # the first call may start a listener


@needs_pickling
def test_a_quoted_secret_is_cut_in_the_message_and_in_the_chained_cause() -> None:
    token = _wire_targets.SecretToken("TOPSECRET-" + "s" * 100_000)
    with pytest.raises(pickle.PicklingError, match=SENT) as info:
        run(_targets.echo, 30.0, args=(token,), mode="process")
    message = str(info.value)
    assert len(message) <= len(SENT) + 2 + 63, message
    assert "s" * 61 not in message
    assert len(str(info.value.__cause__)) <= 303


@needs_pickling
def test_the_message_names_what_could_not_be_pickled() -> None:
    with pytest.raises(pickle.PicklingError, match=SENT) as info:
        run(_targets.echo, 30.0, args=(threading.Lock(),), mode="process")
    assert "'_thread.lock'" in str(info.value)


@needs_pickling
def test_the_notes_pickle_adds_are_the_first_ten_and_a_count_of_the_rest() -> None:
    with pytest.raises(pickle.PicklingError) as info:
        run(
            _targets.echo,
            30.0,
            args=(_wire_targets.nested_dicts(30, threading.Lock()),),
            mode="process",
        )
    notes = getattr(info.value.__cause__, "__notes__", None)
    if not notes:
        pytest.skip("this Python adds no notes to pickling errors")
    assert len(notes) == 11, notes
    assert all(len(note) <= 63 for note in notes[:10]), notes
    assert re.fullmatch(r"\.\.\. and \d+ more notes", notes[10]), notes


@needs_pickling
@pytest.mark.skipif(
    "fork" not in multiprocessing.get_all_start_methods(), reason="no fork start method"
)
def test_a_lock_from_another_context_works_or_raises_the_documented_error() -> None:
    lock = multiprocessing.get_context("fork").Lock()
    try:
        assert run(_wire_targets.count, 30.0, args=(lock,), mode="process") == 1
    except pickle.PicklingError as error:
        assert SENT in str(error)
    assert run(_wire_targets.count, 30.0, args=(1, 2), mode="process") == 2


START_ERRORS: dict[str, Callable[[str], Exception]] = {
    "TypeError": TypeError,
    "ValueError": ValueError,
    "RuntimeError": RuntimeError,
    "PicklingError": pickle.PicklingError,
    "RecursionError": RecursionError,
}


@needs_pickling
@pytest.mark.parametrize("make", list(START_ERRORS.values()), ids=list(START_ERRORS))
@pytest.mark.parametrize("lock_first", [True, False], ids=["lock first", "lock last"])
def test_a_call_that_pickles_for_the_rehearsal_but_not_for_the_start_raises_pickling_error(
    lock_first: bool, make: Callable[[str], Exception]
) -> None:
    lock, once = multiprocessing.Lock(), _wire_targets.OnceThen(make("pickles only once"))
    args = (lock, once) if lock_first else (once, lock)
    with pytest.raises(pickle.PicklingError, match=SENT) as info:
        run(_wire_targets.count, 30.0, args=args, mode="process")
    assert "pickles only once" in str(info.value)
    assert type(info.value.__cause__) is type(once.error)
    assert info.value.__context__ in (None, info.value.__cause__)
    for _ in range(3):
        assert run(_wire_targets.count, 30.0, args=(1, 2), mode="process") == 2


@needs_pickling
def test_the_error_of_a_start_that_cannot_pickle_the_call_is_bounded() -> None:
    once = _wire_targets.OnceThen(TypeError("TOPSECRET-" + "s" * 100_000))
    with pytest.raises(pickle.PicklingError, match=SENT) as info:
        run(_wire_targets.count, 30.0, args=(multiprocessing.Lock(), once), mode="process")
    assert len(str(info.value)) <= len(SENT) + 2 + 63
    assert len(str(info.value.__cause__)) == 303
