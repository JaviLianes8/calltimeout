# calltimeout guide

The [README](https://github.com/JaviLianes8/calltimeout/blob/main/README.md) shows the
basics. This guide covers each mechanism in depth, the errors, nesting and async code.
Every example here is run as a script by the tests.

## The call

`run(fn, timeout, *, args=(), kwargs=None, mode="thread", default=...)` calls
`fn(*args, **kwargs)` and returns its result. `timeout` is a number of seconds: an `int`,
a `float` or another real number such as a `Fraction`, not a `bool`, not negative, not
NaN and at most `threading.TIMEOUT_MAX` (so not infinite). A zero timeout raises at once
without starting the call (in signal mode, so does any timeout under 1 ms). These
checks, and the ones on `fn`, `args`, `kwargs` and `mode`, happen before anything
starts, in every mode. `mode` is one of the three names of `Mode`,
`Literal["thread", "process", "signal"]`, which you can use to annotate your own
wrappers. `kwargs` is copied into a plain `dict` in the caller before the call starts, so
a mapping changed later does not affect the call.

When the budget runs out, `run` raises `CallTimeout`, or returns `default` if one was
given (`None` is a valid default). An exception raised by the call reaches the caller. A
`CallTimeout` from a nested call inside `fn` is not this call's timeout: it propagates
even when this call has a default.

```python
import time

from calltimeout import CallTimeout, run


def inner() -> None:
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

Thread and process mode measure the budget with `time.monotonic()`, so they are as precise
as that clock, whose resolution `time.get_clock_info("monotonic")` reports. On Windows it
is `GetTickCount64()`, about 15.6 ms, up to Python 3.12, and `QueryPerformanceCounter()`
from 3.13.

## Process mode

The call runs in a child process that is terminated when the budget runs out (SIGTERM on
POSIX, `TerminateProcess` on Windows), and killed if it is still alive 1 second later.
The budget covers pickling the call and starting the child. Pickling runs in the caller
and is not interrupted: a slow `__reduce__` overruns the budget by as long as it takes
(and one that never returns blocks `run`), but a call whose pickling used up the budget
is never started. Rebuilding the result also runs in the caller, once the child has sent
it, and is neither counted against the budget nor interrupted: a result whose rebuild is
slow delays `run` by as long (and one that never returns blocks it).

- `fn`, its arguments and its result cross the process boundary, so they must pickle
  (under fork only the result is pickled, see below).
  Targets must be importable: define them at module level, and guard the entry point of
  a script with `if __name__ == "__main__":` as `multiprocessing` requires. Locks, queues,
  pipe ends, sockets, manager proxies and other `multiprocessing` objects can be passed as
  arguments, any number of them, except under forkserver (below). Pipe ends and sockets
  are handed over by the start itself (on Windows, duplicated straight into the child), so
  none is left open in the caller, even when the budget runs out before the child has
  loaded the call.
- A forkserver start sends every descriptor of the call to the fork server in one
  message, which Linux caps. So under forkserver a call carries at most 248 descriptors:
  one per pipe end or socket, two per queue, and one per block of the shared memory that
  `Value` and `Array` objects live in (many share one). A call holding more raises
  `pickle.PicklingError` before any process starts.
- Under spawn and forkserver a call that cannot be pickled (a lambda, a thread lock, a
  pool, an argument nested too deeply) raises `pickle.PicklingError` before any process
  starts, chained from pickle's own error, whose type depends on the Python version.
  A call holding locks or queues is rehearsed as the start will pickle it, so one whose
  contents cannot pickle (a `Value` guarded by a `threading.Lock`) fails the same way.
  One that still fails when the start pickles it again (an object that pickles only once,
  a manager proxy whose pickling raises) raises the same error, and the child created for
  it is stopped before it runs anything. A `KeyboardInterrupt` or other exception that is
  not an `Exception`, raised there, is raised as it is once that child is stopped. Under
  fork nothing is pickled on the way in.
- The child process is named `calltimeout:<function>`, like the thread of thread mode.
- A child that exits without a result (a crash, `os._exit`, the out-of-memory killer)
  raises `CallCrashed` with its exit code as soon as it is gone, not a timeout, and never
  the default. The code is the one `multiprocessing` reports: the value given to
  `os._exit`, or `-N` for a child killed by signal `N` on POSIX.
- An exception from the child arrives with the child's traceback chained as its cause:
  a `RemoteTraceback`, whose text (also its `text` attribute) is that traceback. One that
  cannot be pickled arrives as a `RuntimeError` naming its type and quoting its text.
  `sys.exit()` in the call raises `SystemExit` in the caller like any other exception.
- A result that cannot be pickled raises `pickle.PicklingError` at once, and one the
  parent cannot rebuild raises `pickle.UnpicklingError`.
- After the result arrives the child gets up to 1 second to shut down on its own before
  it is terminated: its non-daemon threads finish, and its atexit handlers run where
  `multiprocessing` runs them in a child (under spawn, and under fork and forkserver from
  Python 3.13).
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
`NotImplementedError`. Some C code checks for signals as it runs (a regular expression
match does), but a long call inside C that does not (sorting a huge list, `sum()` over a
long `range`) is only interrupted once it returns to Python.

- A call that catches the timeout and carries on still ends in `CallTimeout`, once it
  returns. The timer fires once, so a loop that keeps catching `OSError` (which
  `TimeoutError` is) runs on until it gives up.
- An exception raised while handling the timeout counts as the timeout, also one raised
  `from` another cause; `KeyboardInterrupt`, `SystemExit` and unrelated errors propagate.
- No timer is armed for less than 1 ms: a tick due that soon could land before an
  interrupted system call blocks again and be lost, letting a blocking call run to its
  end. So a tick that arrives less than 1 ms before the deadline (an enclosing timer, a
  stray `SIGALRM`) ends the call there, and a timeout under 1 ms ends it at once without
  starting it.
- Timers already armed with `setitimer` or `alarm` keep their schedule and their handler
  still runs when due (up to 1 ms late, by the rule above), so signal-mode calls can be
  nested. An interval timer's ticks stay on its own schedule: the lateness of one tick
  does not carry over to the next. A call that resets `ITIMER_REAL` itself, or installs its own `SIGALRM` handler
  (`SIG_IGN` included, as an alarm-based helper may), cancels the deadline: its result is
  then returned even if the budget ran out. A `SIGALRM` handler installed outside Python
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
method of a module-level class works too, as an instance method, a `staticmethod` or a
`classmethod` (with `with_timeout` applied first, under the method decorator). A
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
| `RuntimeError` | Signal mode outside the main thread, or with a `SIGALRM` handler set outside Python; process mode: the call raised an exception that cannot be pickled (raised in its place, naming its type) |
| `NotImplementedError` | Signal mode on Windows |
| `pickle.PicklingError` | Process mode: `fn` or an argument cannot be sent to the child (raised before the call runs: before any process starts, or once the child is stopped for a call that fails only when the start pickles it), a forkserver call holds more than 248 descriptors, or the result cannot be sent back |
| `pickle.UnpicklingError` | Process mode: the result cannot be rebuilt in the caller |

Both exceptions keep their attribute through pickle and copy, so they can cross process
boundaries themselves. Messages quote at most 60 characters of any value you passed, so
a huge argument never ends up in a log. The error pickle raised, chained as the cause of
the `PicklingError` for a call or a result that cannot be sent, or of the
`UnpicklingError` for a result that cannot be rebuilt (sent back inside the child's
traceback for a result), can quote more: its text is cut after 300 characters, and
only its first ten notes are kept, each cut after 60 characters, then a count of the rest.
That is done in place for the plain errors pickle raises (`TypeError`, `ValueError`,
`RuntimeError`, `AttributeError`, `RecursionError`, `pickle.PicklingError` and a few
more, exactly those types). Any other error, such as one an argument's own `__reduce__`
raised (a subclass, one with a `__str__` of its own), is replaced as the cause by a
`RuntimeError` naming its type and quoting its text, bounded the same way. Errors chained
to the cause are not kept, since they can quote a value too.

## In async code

Coroutines already have `asyncio.timeout()` (Python 3.11+) and `asyncio.wait_for()`, and
`run` refuses coroutine functions with a pointer to them. For a blocking call, run `run`
in a worker thread so the event loop stays free; process mode then really stops the call:

```python
import asyncio
import time

from calltimeout import run


async def main() -> str | None:
    return await asyncio.to_thread(
        run, time.sleep, 0.5, args=(60,), mode="process", default="stopped"
    )


if __name__ == "__main__":
    print(asyncio.run(main()))  # stopped
```
