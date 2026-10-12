"""The public exceptions keep their data across pickle and copy."""

from __future__ import annotations

import copy
import pickle

import pytest

from calltimeout import CallCrashed, CallTimeout


@pytest.mark.parametrize("budget", [0.25, 3])
def test_call_timeout_survives_pickle_and_copy(budget: float) -> None:
    original = CallTimeout(budget)
    for clone in (pickle.loads(pickle.dumps(original)), copy.copy(original)):
        assert type(clone) is CallTimeout
        assert clone.timeout == budget
        assert str(clone) == str(original)


@pytest.mark.parametrize("exitcode", [3, -9, None])
def test_call_crashed_survives_pickle_and_copy(exitcode: int | None) -> None:
    original = CallCrashed(exitcode)
    for clone in (pickle.loads(pickle.dumps(original)), copy.deepcopy(original)):
        assert type(clone) is CallCrashed
        assert clone.exitcode == exitcode
        assert str(clone) == str(original)


def test_the_exceptions_fit_existing_except_clauses() -> None:
    assert issubclass(CallTimeout, TimeoutError)
    assert issubclass(CallCrashed, RuntimeError)
    assert not issubclass(CallCrashed, TimeoutError)


def test_messages_name_the_numbers() -> None:
    assert str(CallTimeout(1.5)) == "call did not finish within 1.5 seconds"
    assert "code 3" in str(CallCrashed(3))
