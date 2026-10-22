# calltimeout guide

The [README](https://github.com/JaviLianes8/calltimeout/blob/main/README.md) shows the
basics. This guide covers each mechanism in depth, the errors, nesting and async code.
Every example here is run as a script by the tests.

## The call

`run(fn, timeout, *, args=(), kwargs=None, mode="thread", default=...)` calls
`fn(*args, **kwargs)` and returns its result. `timeout` is a number of seconds: an `int`,
a `float` or another real number such as a `Fraction`, not a `bool`, not negative, not
NaN and at most `threading.TIMEOUT_MAX` (so not infinite). A zero timeout raises at once
without starting the call. These checks, and the ones on `fn`, `args`, `kwargs` and
`mode`, happen before anything starts, in every mode. `mode` is one of the three names
of `Mode`, `Literal["thread", "process", "signal"]`, which you can use to annotate your
own wrappers. `kwargs` is copied into a plain `dict` in the caller before the call starts,
so a mapping changed later does not affect the call.

When the budget runs out, `run` raises `CallTimeout`, or returns `default` if one was
given (`None` is a valid default). An exception raised by the call reaches the caller. A
`CallTimeout` from a nested call inside `fn` is not this call's timeout: it propagates
even when this call has a default.

```python
import time

from calltimeout import CallTimeout, run


def inner() -> str:
    return run(time.sleep, 0.05, args=(10,))


try:
    run(inner, 5.0, default="outer default")
except CallTimeout as exc:
    print(f"the inner {exc.timeout} second budget ran out")  # the inner 0.05 second budget ran out
```

## Thread mode

The default. The call runs in a daemon thread named `calltimeout:<function>`, in a copy
of the caller's context variables (as `asyncio.to_thread` does), and `run` stops waiting
when the budget runs out. Python cannot stop a running thread, so a call that ignores the
clock keeps running after `run` has raised, until it returns or the process exits. Daemon
threads are stopped abruptly at shutdown, so do not leave one holding a file or a
transaction. Use thread mode for calls that end on their own, eventually.

## Process mode

The call runs in a child process that is terminated when the budget runs out (SIGTERM on
POSIX, `TerminateProcess` on Windows), and killed if it is still alive 1 second later.
The budget covers pickling the call and starting the child.

- `fn`, its arguments and its result cross the process boundary, so they must pickle.
  Targets must be importable: define them at module level, and guard the entry point of
  a script with `if __name__ == "__main__":` as `multiprocessing` requires. Locks, queues
  and other `multiprocessing` objects can be passed as arguments.
- Under spawn and forkserver a call that cannot be pickled (a lambda, a thread lock, a
  pool, an argument nested too deeply) raises `pickle.PicklingError` before any process
  starts, chained from pickle's own error, whose type depends on the Python version.
  Under fork nothing is pickled on the way in.
- The child process is named `calltimeout:<function>`, like the thread of thread mode.
- A child that exits without a result (a crash, `os._exit`, the out-of-memory killer)
  raises `CallCrashed` with its exit code as soon as it is gone, not a timeout, and never
  the default. The code is the one `multiprocessing` reports: the value given to
  `os._exit`, or `-N` for a child killed by signal `N` on POSIX.
- An exception from the child arrives with the child's traceback chained as its cause.
  One that cannot be pickled arrives as a `RuntimeError` naming it. `sys.exit()` in the
  call raises `SystemExit` in the caller like any other exception.
- A result that cannot be pickled raises `pickle.PicklingError` at once, and one the
  parent cannot rebuild raises `pickle.UnpicklingError`.
- After the result arrives the child gets up to 1 second to shut down on its own (atexit
  handlers, non-daemon threads) before it is terminated.
- Processes started by the call itself are not stopped with it.

```python
import os

from calltimeout import CallCrashed, run


def main() -> None:
    try:
        run(os._exit, 30.0, args=(3,), mode="process")
    except CallCrashed as exc:
        print(f"exit code {exc.exitcode}")  # exit code 3

    try:
        run(int, 30.0, args=("ten",), mode="process")
    except ValueError as exc:
        print(type(exc.__cause__).__name__)  # RemoteTraceback


if __name__ == "__main__":
    main()
```

## Signal mode

A `SIGALRM` timer raises `CallTimeout` inside the call, at the line it has reached. Since
PEP 475 a signal handler that raises also stops blocking system calls such as
`time.sleep` or a socket read. It needs no thread and no pickling, but only works in the
main thread on POSIX: in another thread it raises `RuntimeError`, and on Windows
`NotImplementedError`. A long call inside C (a big regular expression match) is only
interrupted once it returns to Python.

- A call that catches the timeout and carries on still ends in `CallTimeout`, once it
  returns. The timer fires once, so a loop that keeps catching `OSError` (which
  `TimeoutError` is) runs on until it gives up.
- An exception raised while handling the timeout counts as the timeout, also one raised
  `from` another cause; `KeyboardInterrupt`, `SystemExit` and unrelated errors propagate.
- A tick that arrives less than 1 ms before the deadline (an enclosing timer, a stray
  `SIGALRM`) ends the call there: re-arming the timer for less could lose the tick and
  let a blocking call run to its end.
- Timers already armed with `setitimer` or `alarm` keep their schedule and their handler
  still runs when due, so signal-mode calls can be nested; a call that resets
  `ITIMER_REAL` itself cancels the deadline. A `SIGALRM` handler installed outside Python
  is refused, because it could not be restored.

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

## The decorator

`with_timeout(timeout, *, mode="thread", default=...)` makes every call of the decorated
function go through `run`. Type checkers keep checking each call against the original
parameters, and the result type becomes `T | D` with a default. The settings are checked
when the decorator is made, and the function when it is applied. Signal mode's platform
and main-thread checks run at each call instead, since a decorated function can be called
from any thread: on Windows the decorator is made, and each call raises
`NotImplementedError`.

In process mode under spawn or forkserver the child imports the function by name, so
either the decorated function or the original must be reachable under its module and
name: a plain `@with_timeout` at module level, or `fast = with_timeout(...)(slow)`. A
callable that pickles by value (a `functools.partial`, a callable object) is sent as it is.
Each call runs in its own child, also a call made from inside the function's own child
(a recursive function gets a new child, with its own budget, for every level).

```python
import time

from calltimeout import with_timeout


@with_timeout(0.05, default=None)
def lookup(key: str) -> str:
    time.sleep(1.0)
    return key.upper()


print(lookup("id"))  # None
```

## Errors

| Raised | When |
|---|---|
| `CallTimeout` (a `TimeoutError`) | The budget ran out and no default was given |
| `CallCrashed` (a `RuntimeError`) | Process mode: the child exited without a result |
| `TypeError` | `timeout` is not a real number (or one that fails to convert to `float`), `fn` is not callable or is a coroutine function, `args` is not a tuple, `kwargs` is not a mapping of `str` keys, `mode` is not a `str`, or the call returned a coroutine |
| `ValueError` | `timeout` is negative, NaN or above `threading.TIMEOUT_MAX`, or `mode` is not one of the three names |
| `RuntimeError` | Signal mode outside the main thread, or with a `SIGALRM` handler set outside Python |
| `NotImplementedError` | Signal mode on Windows |
| `pickle.PicklingError` | Process mode: `fn` or an argument cannot be sent to the child (raised before any process starts), or the result cannot be sent back |
| `pickle.UnpicklingError` | Process mode: the result cannot be rebuilt in the caller |

Both exceptions keep their attribute through pickle and copy, so they can cross process
boundaries themselves. Messages quote at most 60 characters of any value you passed, so
a huge argument never ends up in a log.

## In async code

Coroutines already have `asyncio.timeout()` (Python 3.11+) and `asyncio.wait_for()`, and
`run` refuses coroutine functions with a pointer to them. For a blocking call, run `run`
in a worker thread so the event loop stays free; process mode then really stops the call:

```python
import asyncio
import time

from calltimeout import run


async def main() -> str:
    return await asyncio.to_thread(
        run, time.sleep, 0.5, args=(60,), mode="process", default="stopped"
    )


if __name__ == "__main__":
    print(asyncio.run(main()))  # stopped
```
