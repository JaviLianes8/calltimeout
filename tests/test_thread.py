"""Thread mode: the default mechanism."""

from __future__ import annotations

import contextvars
import threading
from collections.abc import Iterator

import _targets
import pytest

from calltimeout import CallTimeout, run

request_id: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="unset")


@pytest.fixture
def closed_gate() -> Iterator[None]:
    _targets.gate.clear()
    yield
    _targets.gate.set()


def test_returns_the_value_when_the_call_finishes_in_time() -> None:
    assert run(_targets.echo, 1.0, args=("ok",)) == "ok"


def test_passes_keyword_arguments_to_the_call() -> None:
    assert run(_targets.echo, 1.0, kwargs={"value": 7}) == 7


@pytest.mark.usefixtures("closed_gate")
def test_raises_call_timeout_carrying_the_budget() -> None:
    with pytest.raises(CallTimeout) as info:
        run(_targets.blocks_until_gate, 0.05)
    assert info.value.timeout == 0.05
    assert isinstance(info.value, TimeoutError)


@pytest.mark.usefixtures("closed_gate")
def test_returns_the_default_on_timeout_instead_of_raising() -> None:
    assert run(_targets.blocks_until_gate, 0.05, default="fallback") == "fallback"


def test_a_default_of_none_is_returned_too() -> None:
    _targets.gate.clear()
    try:
        assert run(_targets.blocks_until_gate, 0.05, default=None) is None
    finally:
        _targets.gate.set()


def test_propagates_an_exception_raised_by_the_call() -> None:
    with pytest.raises(ValueError, match="boom"):
        run(_targets.boom, 1.0)


def test_the_call_sees_the_callers_context_variables() -> None:
    token = request_id.set("abc")
    try:
        assert run(request_id.get, 1.0) == "abc"
    finally:
        request_id.reset(token)


def test_context_changes_inside_the_call_stay_inside() -> None:
    run(request_id.set, 1.0, args=("changed",))
    assert request_id.get() == "unset"


@pytest.mark.usefixtures("closed_gate")
def test_a_lingering_call_runs_in_a_named_daemon_thread() -> None:
    with pytest.raises(CallTimeout):
        run(_targets.blocks_until_gate, 0.05)
    lingering = [t for t in threading.enumerate() if t.name.startswith("calltimeout:")]
    assert any(t.name == "calltimeout:blocks_until_gate" for t in lingering)
    assert all(t.daemon for t in lingering)


def test_a_nested_timeout_is_not_mistaken_for_this_calls_own() -> None:
    with pytest.raises(CallTimeout) as info:
        run(_targets.nested_timeout, 30.0, default="outer default")
    assert info.value.timeout == 0.05
