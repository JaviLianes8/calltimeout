# calltimeout

Run a callable with a wall-clock timeout and get a typed result or a clean
`TimeoutError`, with an honest choice of mechanism.

## Install

```
pip install calltimeout
```

Python 3.10 or newer, no dependencies.

## Usage

```python
import time

from calltimeout import CallTimeout, run


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
```

`run(fn, timeout, *, args=(), kwargs=None, mode="thread", default=...)` passes `args`
and `kwargs` to `fn`. The timeout is a number of seconds: an `int` or `float`, not
negative, not NaN and not infinite. A zero timeout raises at once without starting the
call. Exceptions raised by the call reach the caller (in process mode as a pickled copy,
see below). `default` is only used
for this call's own timeout: a `CallTimeout` from a nested call inside `fn` propagates.
`Mode` is the `Literal` type of the three mode names, for annotating your own wrappers.

### As a decorator

`with_timeout` keeps the decorated function's parameters, so type checkers still check
every call, and the result type becomes `T | D` when a default is given. In process mode
under spawn or forkserver the child imports the function by name, so either the
decorated function or the original must be reachable under its module and name (a
plain `@with_timeout` at module level, or `fast = with_timeout(...)(slow)`):

```python
import time

from calltimeout import with_timeout


@with_timeout(2.0)
def add(left: int, right: int) -> int:
    return left + right


@with_timeout(0.05, default=None)
def lookup(key: str) -> str:
    time.sleep(1.0)
    return key.upper()


print(add(2, 3))  # 5
print(lookup("id"))  # None
```

## Choosing a mechanism

The trade-off is the whole point of the library, so it is stated plainly:

| | `"thread"` (default) | `"process"` | `"signal"` |
|---|---|---|---|
| Stops a runaway call | No: it keeps running in a daemon thread | Yes: terminated, and killed if still alive 1 second later | Python code and blocking system calls: yes. A long call inside C: once it returns |
| Where it works | Everywhere | Everywhere | POSIX, main thread only |
| Pickling | Not needed | `fn`, its arguments and its result | Not needed |
| Cost | A thread | A new process, whose start counts against the budget | A timer |
| Context variables | A copy of the caller's, like `asyncio.to_thread` | Not shared | Shared: same thread |

**Thread mode** runs the call in a daemon thread named `calltimeout:<function>` and
stops waiting after the timeout. Python cannot stop a running thread, so a call that
ignores the clock (a tight loop, a blocking call without its own timeout) keeps running
after `run` has raised, until it returns or the process exits. Daemon threads are
stopped abruptly at shutdown, so do not leave one holding a file or a transaction.

**Process mode** runs the call in a child process and really stops it on overrun. A
child that exits without a result (a crash, `os._exit`, the out-of-memory killer)
raises `CallCrashed` with its exit code as soon as it is gone, instead of a timeout. An
exception from the child arrives with the child's traceback chained as its cause, and a
result that cannot be pickled raises `pickle.PicklingError` straight away (and one the
parent cannot rebuild, `pickle.UnpicklingError`). An exception that cannot be pickled
arrives as a `RuntimeError` naming it, and `sys.exit()` in the call raises `SystemExit`
in the caller like any other exception. After the result arrives the child gets up to
1 second to shut down on its own (atexit handlers, non-daemon threads) before it is
terminated. Locks, queues and other `multiprocessing` objects can be passed as
arguments. Processes started by the call itself are not stopped with it. Targets must be importable, so
define them at module level, and guard the entry point of a script with
`if __name__ == "__main__":` as `multiprocessing` requires.

```python
import math
import os
import time

from calltimeout import CallCrashed, run

print(run(math.factorial, 30.0, args=(20,), mode="process"))  # 2432902008176640000

# The child is terminated, not left running.
print(run(time.sleep, 0.5, args=(60,), mode="process", default="stopped"))  # stopped

try:
    run(os._exit, 30.0, args=(3,), mode="process")
except CallCrashed as exc:
    print(f"exit code {exc.exitcode}")  # exit code 3
```

**Signal mode** arms a `SIGALRM` timer and raises `CallTimeout` inside the call, at the
line it has reached. Since PEP 475 a signal handler that raises also stops blocking
system calls such as `time.sleep` or a socket read. It needs no thread and no pickling,
but it only works in the main thread on POSIX: elsewhere it raises `RuntimeError`, and
on Windows `NotImplementedError`. A call that catches the timeout and carries on still
ends in `CallTimeout`, but only once it returns: the timer fires once, so a loop that
keeps catching `OSError` (which `TimeoutError` is) runs on until it gives up. An
exception raised while handling the timeout counts as the timeout; `KeyboardInterrupt`,
`SystemExit` and unrelated errors propagate. Timers already armed with `setitimer` or
`alarm` keep their schedule, so signal-mode calls can be nested, but a call that resets
`ITIMER_REAL` itself cancels the deadline.

```python
import sys
import time

from calltimeout import CallTimeout, run

if sys.platform != "win32":
    try:
        run(time.sleep, 0.1, args=(60,), mode="signal")
    except CallTimeout as exc:
        # The timeout was raised inside time.sleep and is chained as the cause.
        print(f"interrupted: {type(exc.__cause__).__name__}")  # interrupted: CallTimeout
```

## In async code

Coroutines already have `asyncio.timeout()`, and `run` refuses coroutine functions
with a pointer to it. For a blocking call, run `run` in a worker thread so the event
loop stays free; process mode then really stops the call:

```python
import asyncio
import time

from calltimeout import run


async def main() -> str:
    return await asyncio.to_thread(
        run, time.sleep, 0.5, args=(60,), mode="process", default="stopped"
    )


print(asyncio.run(main()))  # stopped
```

## Why

Running a function under a timeout is a common need, but the usual packages have
gone stale and ship no type information:

- [`func-timeout`](https://pypi.org/project/func-timeout/): last release 2019.
- [`stopit`](https://pypi.org/project/stopit/): last release 2018.
- [`timeout-decorator`](https://pypi.org/project/timeout-decorator/): last
  release 2020.

Beyond age, most of them hide the mechanism and quietly imply they can always
cancel the work, which a thread cannot. `calltimeout` is small, fully typed
(`mypy --strict`, `py.typed`), depends on nothing, and makes the choice between
thread, process and signal explicit rather than a hidden surprise.

## License

MIT. See [LICENSE](LICENSE).

## Links

- Website: https://lianes8studio.com
- GitHub: https://github.com/JaviLianes8
- LinkedIn: https://www.linkedin.com/in/jlianes/
