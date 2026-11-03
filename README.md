# calltimeout

[![Lianes8 Certified](https://lianes8studio.com/certified/lianes8-certified-badge.svg)](https://lianes8studio.com/certified)

Run a callable with a wall-clock timeout and get a typed result or a clean
`TimeoutError`, with an honest choice of mechanism.

A call that hangs (a network read without a timeout, a runaway loop, a stuck library)
takes its caller down with it. Putting a time limit on it looks easy and is not: a thread
cannot be stopped, a process needs everything to pickle, and a signal only works in the
main thread on POSIX. `calltimeout` offers all three behind one typed function and says
plainly what each one can and cannot do.

## Install

```
pip install calltimeout
```

Python 3.10 or newer, no dependencies.

## Usage

```python
import time

from calltimeout import CallTimeout, run, with_timeout


def fetch(delay: float) -> str:
    time.sleep(delay)
    return "payload"


# The result, when the call finishes in time.
print(run(fetch, 2.0, args=(0.01,)))  # payload

# CallTimeout, a subclass of TimeoutError, when it does not.
try:
    run(fetch, 0.05, args=(1.0,))
except CallTimeout as exc:
    print(f"gave up after {exc.timeout} seconds")  # gave up after 0.05 seconds

# Or a fallback instead of raising.
print(run(fetch, 0.05, args=(1.0,), default="cached"))  # cached


# The same as a decorator that keeps the function's signature for type checkers.
@with_timeout(2.0)
def add(left: int, right: int) -> int:
    return left + right


print(add(2, 3))  # 5
```

## Choosing a mechanism

The trade-off is the whole point of the library, so it is stated plainly:

| | `"thread"` (default) | `"process"` | `"signal"` |
|---|---|---|---|
| Stops a runaway call | No: it keeps running in a daemon thread | Yes: terminated, and killed if still alive 1 second later | Python code and blocking system calls: yes. A long call inside C: once it returns |
| Where it works | Everywhere | Everywhere | POSIX, main thread only |
| Pickling | Not needed | The result always; `fn` and its arguments under spawn and forkserver | Not needed |
| Cost | A thread | A new process, whose start and the transfer of its result count against the budget | A timer |
| Context variables | A copy of the caller's, like `asyncio.to_thread` | A copy under fork, the defaults under spawn and forkserver; changes never come back | Shared: same thread |

```python
import math
import time

from calltimeout import run


def main() -> None:
    # Process mode really stops the work: the child is terminated, not left running.
    print(run(time.sleep, 0.5, args=(60,), mode="process", default="stopped"))  # stopped
    print(run(math.factorial, 30.0, args=(20,), mode="process"))  # 2432902008176640000


if __name__ == "__main__":
    main()
```

Process mode needs importable targets and, in a script, the
`if __name__ == "__main__":` guard that `multiprocessing` asks for, as above: under the
spawn and forkserver start methods the child imports the script again. The
[GUIDE](https://github.com/JaviLianes8/calltimeout/blob/main/GUIDE.md) explains each mode
in depth, every error and its cause, nesting, and use from async code.

## API

| Name | What it is |
|---|---|
| `run(fn, timeout, *, args=(), kwargs=None, mode="thread", default=...)` | Call `fn(*args, **kwargs)` with a budget of `timeout` seconds and return its result |
| `with_timeout(timeout, *, mode="thread", default=...)` | The same as a decorator; the decorated function keeps its parameters |
| `CallTimeout` | A `TimeoutError` raised when the budget runs out; `.timeout` is the budget |
| `CallCrashed` | A `RuntimeError` raised in process mode when the child dies without a result; `.exitcode` |
| `RemoteTraceback` | The cause chained to an exception from a process-mode call; its text (`.text`) is the child's traceback |
| `Mode` | `Literal["thread", "process", "signal"]`, for annotating your own wrappers |

Bad arguments raise `TypeError` or `ValueError` before anything starts. In process mode
under the spawn and forkserver start methods, a call that cannot be pickled raises
`pickle.PicklingError` before the call runs (fork pickles only the result). The
[CHANGELOG](https://github.com/JaviLianes8/calltimeout/blob/main/CHANGELOG.md) lists what
changed in each release; from 1.0.0 on the API follows Semantic Versioning.

## Why

Checked on PyPI on 2026-10-22:

- [`pebble`](https://pypi.org/project/pebble/) (5.2.3, maintained and typed) runs calls
  in threads, processes and pools, and reports a crashed process with its exit code. Its
  decorators return a `Future` instead of the result, and its thread decorator takes no
  timeout, since a thread cannot be stopped. It is the better choice for pools of work.
- [`wrapt-timeout-decorator`](https://pypi.org/project/wrapt-timeout-decorator/) (1.5.1,
  February 2024, typed) uses signals by default and can run the call in a subprocess
  instead; it installs six runtime dependencies (`wrapt`, `multiprocess`, `dill`, `psutil`
  and two helpers).
- [`func-timeout`](https://pypi.org/project/func-timeout/) (last release 2019),
  [`stopit`](https://pypi.org/project/stopit/) (2018) and
  [`timeout-decorator`](https://pypi.org/project/timeout-decorator/) (2020) ship no
  type information and have not had a release in years.

`calltimeout` does one thing: a blocking call with a deadline that returns the plain,
typed result. It depends on nothing, is checked with `mypy --strict`, ships `py.typed`,
keeps the decorated function's signature (`ParamSpec`), and makes the choice between
thread, process and signal explicit, with the limits of each written down and tested.

## Development

`pip install -r requirements-dev.txt`, then `scripts/check.ps1` runs format, lint, types
and tests. `python scripts/fetch_upstream.py` downloads the CPython documentation pages
listed in `tests/upstream/MANIFEST.json`, which some tests read (they skip without them),
and `pip install pebble` adds a second implementation the process tests compare against.
Set `CALLTIMEOUT_E2E=1` to also build the wheel and sdist and test the installed package,
and `CALLTIMEOUT_START_METHOD` to run under `spawn`, `fork` or `forkserver`.

## License

MIT. See [LICENSE](https://github.com/JaviLianes8/calltimeout/blob/main/LICENSE).

## Links

- Website: https://lianes8studio.com
- GitHub: https://github.com/JaviLianes8
- LinkedIn: https://www.linkedin.com/in/jlianes/
