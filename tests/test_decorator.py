"""with_timeout: the decorator form keeps the signature and works in every mode."""

from __future__ import annotations

import os
import sys

import _lazy_targets
import _method_targets
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


def test_attributes_set_on_the_wrapped_function_are_kept() -> None:
    def tagged() -> int:
        return 1

    tagged.marker = "kept"  # type: ignore[attr-defined]
    assert with_timeout(5.0)(tagged).marker == "kept"  # type: ignore[attr-defined]


def test_process_mode_sends_a_callable_from_a_module_whose_getattr_raises() -> None:
    # Looking the wrapper up by name hits the module's lazy __getattr__, which raises
    # ImportError: that only means the wrapper cannot be found, so the callable is sent.
    double = with_timeout(30.0, mode="process")(_lazy_targets.Double())
    assert double(21) == 42


def test_process_mode_runs_methods_of_every_kind_in_their_own_child() -> None:
    # A classmethod's wrapper is found by name only as a bound method, which pickle
    # cannot send as the function: it is sent through its class instead.
    here = os.getpid()
    box, sub = _method_targets.Box, _method_targets.Sub
    calls = [
        (box().method(1), ("Box", 1)),
        (sub().method(2), ("Sub", 2)),
        (box.static(3), (3,)),
        (box.klass(4), ("Box", 4)),
        (sub.klass(5), ("Sub", 5)),
        (sub().klass(6), ("Sub", 6)),
    ]
    for got, expected in calls:
        assert got[:-1] == expected
        assert got[-1] != here


def test_applying_the_decorator_to_something_not_callable_raises_at_once() -> None:
    with pytest.raises(TypeError, match="fn must be callable, not int"):
        with_timeout(1.0)(42)  # type: ignore[arg-type]


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
