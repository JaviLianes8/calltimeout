"""with_timeout: the decorator form keeps the signature and works in every mode."""

from __future__ import annotations

import os
import sys

import _targets
import pytest

from calltimeout import CallTimeout, with_timeout

posix_only = pytest.mark.skipif(sys.platform == "win32", reason="SIGALRM is POSIX")


@with_timeout(1.0)
def add(left: int, right: int = 1) -> int:
    """Add two numbers."""
    return left + right


@with_timeout(0.05, default="late")
def waits_for_gate() -> str:
    return _targets.blocks_until_gate()


def test_the_decorated_function_returns_its_result() -> None:
    assert add(2, right=3) == 5


def test_metadata_of_the_wrapped_function_is_kept() -> None:
    assert add.__name__ == "add"
    assert add.__doc__ == "Add two numbers."
    assert add.__wrapped__(1) == 2  # type: ignore[attr-defined]


def test_a_timed_out_call_returns_the_default() -> None:
    _targets.gate.clear()
    try:
        assert waits_for_gate() == "late"
    finally:
        _targets.gate.set()


def test_a_timed_out_call_raises_without_a_default() -> None:
    @with_timeout(0.05)
    def stuck() -> str:
        return _targets.blocks_until_gate()

    _targets.gate.clear()
    try:
        with pytest.raises(CallTimeout):
            stuck()
    finally:
        _targets.gate.set()


def test_process_mode_runs_the_body_once_in_one_child() -> None:
    # A wrapper that started another child from inside its child would never return.
    assert _targets.decorated_pid(0) != os.getpid()


def test_process_mode_stops_an_overrun_and_returns_the_default() -> None:
    assert _targets.decorated_slow(30.0) == "stopped"


@posix_only
def test_signal_mode_interrupts_the_body() -> None:
    @with_timeout(0.1, mode="signal", default="interrupted")
    def spins() -> int:
        return _targets.spin(30.0)

    assert spins() == "interrupted"
