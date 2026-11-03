"""A supplied process decorator retains its own budget and default inside run."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from calltimeout import CallTimeout, run, with_timeout


@with_timeout(0, mode="process", default="skipped")
def zero_work(marker: str) -> str:
    Path(marker).write_text("called", encoding="utf-8")
    return "body ran"


@with_timeout(0.1, mode="process", default="inner timeout")
def slow_default() -> str:
    time.sleep(1)
    return "finished"


@with_timeout(0.1, mode="process")
def slow_raise() -> str:
    time.sleep(1)
    return "finished"


def test_generic_process_call_preserves_zero_budget_and_no_call(tmp_path: Path) -> None:
    marker = tmp_path / "marker"
    assert run(zero_work, 10, args=(str(marker),), mode="process") == "skipped"
    assert not marker.exists()


def test_generic_process_call_preserves_inner_default() -> None:
    assert run(slow_default, 10, mode="process", default="outer") == "inner timeout"


def test_generic_process_call_propagates_inner_timeout() -> None:
    with pytest.raises(CallTimeout) as info:
        run(slow_raise, 10, mode="process", default="outer")
    assert info.value.timeout == 0.1
