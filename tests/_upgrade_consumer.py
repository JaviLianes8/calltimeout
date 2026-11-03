"""Exercise unchanged contracts and persisted exceptions before and after a PyPI upgrade."""

from __future__ import annotations

import contextvars
import importlib.metadata
import inspect
import json
import os
import pickle
import random
import sys
import time
from pathlib import Path

import calltimeout
from calltimeout import CallCrashed, CallTimeout, Mode, run, with_timeout


@with_timeout(30.0, mode="process")
def identity(value: int) -> int:
    return value


def main() -> None:
    version = sys.argv[1]
    assert importlib.metadata.version("calltimeout") == version
    assert calltimeout.__version__ == version
    assert "site-packages" in calltimeout.__file__
    assert list(inspect.signature(identity).parameters) == ["value"]
    rng = random.Random(20261102)
    values: list[object] = []
    modes: tuple[Mode, ...] = ("thread", "process")
    for mode in modes:
        for _ in range(20):
            args = rng.randrange(-1000, 1000), rng.randrange(0, 30), 97
            expected = pow(*args)
            result = run(pow, 30.0, args=args, mode=mode)
            assert result == expected
            values.append(result)
        assert run(time.sleep, 0.05, args=(30,), mode=mode, default=None) is None
        try:
            run(int, 30.0, args=("bad integer",), mode=mode)
        except ValueError as exc:
            values.append([type(exc).__name__, list(exc.args)])
        else:
            raise AssertionError("the call's error was not propagated")
    assert identity(42) == 42
    marker = contextvars.ContextVar("marker", default="unset")
    marker.set("caller")
    assert run(marker.get, 30.0) == "caller"
    try:
        run(os._exit, 30.0, args=(7,), mode="process")
    except CallCrashed as exc:
        assert exc.exitcode == 7
    else:
        raise AssertionError("child crash was not reported")
    saved = Path(__file__).with_suffix(".pickle")
    if version == "0.2.0":
        saved.write_bytes(pickle.dumps((CallTimeout(0.5), CallCrashed(7))))
    timeout, crash = pickle.loads(saved.read_bytes())
    assert type(timeout) is CallTimeout and timeout.timeout == 0.5
    assert type(crash) is CallCrashed and crash.exitcode == 7
    values.extend([str(timeout), str(crash)])
    print(json.dumps(values))


if __name__ == "__main__":
    main()
