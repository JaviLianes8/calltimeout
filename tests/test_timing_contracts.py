"""How soon an overrun is reported, and a result that arrives as the child exits."""

from __future__ import annotations

import multiprocessing
import threading
import time
from collections.abc import Sequence
from multiprocessing.connection import wait

import _targets
import pytest

from calltimeout import CallTimeout, _process, run


def test_thread_mode_raises_within_a_small_margin_of_the_budget() -> None:
    release = threading.Event()
    elapsed: list[float] = []
    try:
        for _ in range(3):
            started = time.monotonic()
            with pytest.raises(CallTimeout):
                run(release.wait, 0.2, args=(30.0,))
            elapsed.append(time.monotonic() - started)
    finally:
        release.set()
    # The best of three, so a busy machine cannot fail it; any added wait still shows. The
    # budget is read with time.monotonic(), which ticks every 15.6 ms on Windows before 3.13.
    tick = time.get_clock_info("monotonic").resolution
    assert 0.2 - tick <= min(elapsed) < 0.3, elapsed


def test_process_mode_never_sleeps_past_the_deadline(monkeypatch: pytest.MonkeyPatch) -> None:
    # A poll interval far longer than the budget: the last wait must still be cut to it.
    monkeypatch.setattr(_process, "POLL", 20.0)
    started = time.monotonic()
    with pytest.raises(CallTimeout):
        run(_targets.slow, 1.0, args=(30.0,), mode="process")
    elapsed = time.monotonic() - started
    assert 1.0 <= elapsed < 1.0 + _process.GRACE, elapsed
    assert multiprocessing.active_children() == []


def test_a_result_sent_as_the_child_exits_is_returned(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[float | None] = []

    def wait_misses_it(objects: Sequence[object], timeout: float | None = None) -> list[object]:
        calls.append(timeout)
        if len(calls) == 1:
            # The child sends its result and exits while this wait is timing out.
            wait([objects[-1]], 30.0)  # type: ignore[list-item]
            return []
        return list(wait(objects, timeout))  # type: ignore[arg-type]

    monkeypatch.setattr(_process, "wait", wait_misses_it)
    assert run(pow, 10.0, args=(2, 5), mode="process") == 32
    assert len(calls) == 1
