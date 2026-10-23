"""A consumer of the installed package, run by tests/test_e2e_wheel.py in a fresh venv."""

from __future__ import annotations

import importlib.metadata
import importlib.resources
import inspect
import os
import pickle
import sys
import time
from typing import get_args

import calltimeout
from calltimeout import CallCrashed, CallTimeout, Mode, run, with_timeout


@with_timeout(30.0, mode="process")
def child_pid(offset: int) -> int:
    return os.getpid() + offset


@with_timeout(0.5, mode="process", default="stopped")
def runaway() -> str:
    time.sleep(60)
    return "finished"


def explode() -> None:
    raise KeyError("missing")


if __name__ == "__main__":
    assert "site-packages" in calltimeout.__file__, calltimeout.__file__
    assert importlib.metadata.version("calltimeout") == calltimeout.__version__
    assert importlib.resources.files("calltimeout").joinpath("py.typed").is_file()

    assert sorted(calltimeout.__all__) == [
        "CallCrashed",
        "CallTimeout",
        "Mode",
        "run",
        "with_timeout",
    ]
    assert get_args(Mode) == ("thread", "process", "signal")
    assert list(inspect.signature(child_pid).parameters) == ["offset"]
    clone = pickle.loads(pickle.dumps(CallTimeout(0.25)))
    assert type(clone) is CallTimeout and clone.timeout == 0.25
    assert CallTimeout.__module__ == CallCrashed.__module__ == "calltimeout"
    total: int = run(pow, 5.0, args=(2, 10))
    assert total == 1024
    assert run(time.sleep, 0.05, args=(1.0,), default="late") == "late"
    assert child_pid(0) != os.getpid()
    started = time.monotonic()
    assert runaway() == "stopped"
    assert time.monotonic() - started < 10
    try:
        run(os._exit, 30.0, args=(7,), mode="process")
    except CallCrashed as exc:
        assert exc.exitcode == 7
    else:
        raise AssertionError("crash not reported")
    try:
        run(explode, 30.0, mode="process")
    except KeyError as exc:
        assert "raise KeyError" in str(exc.__cause__)
    else:
        raise AssertionError("child error not raised")
    if sys.platform != "win32":
        try:
            run(time.sleep, 0.1, args=(60,), mode="signal")
        except CallTimeout as exc:
            assert exc.timeout == 0.1
        else:
            raise AssertionError("signal mode did not interrupt")
    print("e2e ok")
