# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.0] - 2026-10-22

The public API is now stable: `run`, `with_timeout`, `CallTimeout`, `CallCrashed` and
`Mode`, with their parameter names, defaults and exception types, follow Semantic
Versioning from this release on. calltimeout was never published before 1.0.0, and
0.1.0 and 0.2.0 were never tagged; the changes below are against 0.2.0, commit 9b6975c
on `main`.

### Changed

- A `mode` that is not a `str` raises `TypeError` (it raised `ValueError`); an unknown
  mode name still raises `ValueError`, and the message lists the three valid names. A
  `str` subclass is read as the plain name.
- `CallTimeout` and `CallCrashed` are shown and pickled as `calltimeout.CallTimeout` and
  `calltimeout.CallCrashed`, so a pickle never names a private module, and they keep
  extra attributes (such as notes) through pickle and copy.
- A real-number timeout whose conversion to `float` fails raises `TypeError` (the
  conversion's own error is chained as the cause).
- Error messages are bounded: a quoted value or name is cut after 60 characters, a
  quoted exception after 300 (60 for pickle's error about a call that cannot be sent,
  which can quote an argument), and an integer of more than 64 bits is described by its
  size instead of printed.
- Process mode: the budget also covers pickling the call and starting the child, and a
  call whose pickling used it up is never started. A child that cannot load the call
  (a function the child cannot import under spawn or forkserver) reports that error
  with its traceback instead of a crash with exit code 1. A child that dies while
  sending its result raises `CallCrashed`, and waiting for a crashed child's exit code
  never runs past the budget. A result that cannot be pickled raises
  `pickle.PicklingError` with the child's traceback of the failure.
- Process mode: a call whose function or arguments cannot be pickled raises
  `pickle.PicklingError` before any process starts, chained from pickle's own error
  (which was raised as it was, a different type on each Python version). That error is
  bounded in place: its text is cut after 300 characters, and only its first ten notes
  are kept, each cut after 60 characters, followed by a count of the rest; one whose text
  cannot be cut in place (a `__str__` of its own, `args` that cannot be set) is replaced
  as the cause by a `RuntimeError` naming its type, bounded the same way. A call holding
  objects that `multiprocessing` only pickles while a child starts (locks, queues, shared
  values), any number of them, is first rehearsed as the start will pickle it, so one
  whose contents cannot pickle (a `Value` guarded by a `threading.Lock`) fails the same
  way, and one that still fails when the start pickles it again (an object that pickles
  only once) raises the same error, its child stopped before it runs anything. An
  argument whose pickling raised `NotImplementedError` (a pool), `RecursionError` or a
  `RuntimeError` used to fail after the child was created, and on Windows it then broke
  the next process-mode call.
- Process mode: the call's function and arguments are pickled once, before the start;
  only its pipe ends, sockets and manager proxies, or the whole call when it holds locks
  or queues, are pickled by the start itself. Pipe ends and sockets are handed to the
  child by that start (POSIX passes the descriptors with it, Windows duplicates them
  straight into the child), so none is left open in the caller, even when the budget
  runs out while pickling the call or before the child has loaded it. Such a call left a
  duplicate of each one open in the caller (on Windows also one of the result pipe,
  whatever the call held; under forkserver the caller also printed `ConnectionResetError`
  tracebacks), so the reader of that pipe never saw its end and handles ran out. A
  manager proxy goes with its manager's authkey, as `multiprocessing` sends it: one of a
  manager with its own authkey failed in the child with `AuthenticationError` unless the
  call also held a lock. An argument whose `__class__` raises is sent as it pickles.
- `with_timeout` in process mode sends a callable that pickles by value (a
  `functools.partial`, a callable object) as it is, as `run` does; it failed with
  `AttributeError` under spawn and forkserver.
- A callable whose `__getattr__` raises something other than `AttributeError` is run
  like any other; that error escaped from the coroutine check in `run` and
  `with_timeout`.
- `timeout` is annotated `float | numbers.Real` in `run` and `with_timeout`, so type
  checkers accept a `Fraction`, which already worked.
- Signal mode: an exception raised with an explicit cause while handling the timeout
  (`raise E from other`) counts as the timeout, like `raise E` and `raise E from None`;
  it escaped as `E`.
- Signal mode: no timer is armed for less than 1 ms, so a timer tick less than 1 ms
  before the deadline ends the call there, a timeout under 1 ms ends it at once without
  starting it (like a zero timeout), and an enclosing timer due sooner than 1 ms has its
  handler run up to 1 ms late. A timer that short could fire before the interrupted
  system call blocked again, so a blocking call overran by its whole length.
- Signal mode: a timer tick that lands after the call has finished can no longer re-arm
  the timer.
- Thread mode measures the budget from the start of `run`, including starting the thread.
- The coroutine error names `asyncio.wait_for()` as well as `asyncio.timeout()`, which
  only exists from Python 3.11.
- Every public name has a docstring with an example that runs as a doctest, `Mode` in
  the package docstring (typing caches `Literal` aliases, so a docstring of its own would
  relabel the caller's identical aliases), and a new GUIDE covers each mode, every
  error and use from async code. The process-mode examples guard their entry point and
  are tested as scripts.
- `Development Status :: 5 - Production/Stable`.

## [0.2.0] - 2026-10-12

Never published or tagged (commit 9b6975c on `main`).

### Added

- `mode="signal"`: a SIGALRM timer raises `CallTimeout` inside the call, which stops
  pure Python code and blocking system calls in place. POSIX main thread only; other
  threads get `RuntimeError` and Windows `NotImplementedError`. Timers already armed
  keep their schedule (a raising outer handler runs once), so calls can be nested, and
  a call that swallows the timeout still ends in `CallTimeout` when it returns, while
  `KeyboardInterrupt`, `SystemExit` and unrelated errors propagate.
- `with_timeout(timeout, *, mode, default)`: a decorator that keeps the wrapped
  function's signature for type checkers (`ParamSpec`), in every mode including process
  mode for functions the child can import by name (decorated in place or assigned to a
  new name).
- `CallCrashed`: raised in process mode when the child exits without a result, with its
  exit code, as soon as it is gone.

### Changed

- Process mode waits on the result pipe and the process together, pickles results and
  errors in the child (an unpicklable result raises `pickle.PicklingError` at once, an
  unpicklable exception arrives as a `RuntimeError` stand-in), chains the child's
  traceback as the cause, kills a child that ignores SIGTERM after 1 second, and stops
  the child whenever the caller leaves early, including on `KeyboardInterrupt`.
- Process mode notices a crashed child even while a grandchild it forked keeps the
  pipes open.
- Process mode pickles the call before starting the child, so a failed start cannot
  leave the next call reading from a stale pipe on Windows; locks and queues, which
  only pickle during start, are still passed through.
- A finished child gets up to 1 second to exit on its own before it is terminated; a
  result the parent cannot unpickle raises `pickle.UnpicklingError`.
- `default` is returned only for the call's own timeout; a `CallTimeout` from a nested
  call propagates.
- Thread mode runs the call in a copy of the caller's context variables and names the
  thread `calltimeout:<function>`.
- `timeout` must be a real number (not a bool), not NaN and at most
  `threading.TIMEOUT_MAX`; a zero timeout raises without starting the call. Coroutine
  functions and coroutine results are rejected with a pointer to `asyncio.timeout`.
  `kwargs` must be a mapping, and `run` and `with_timeout` reject modes the same way.
- `CallTimeout` keeps its `timeout` through pickle and copy, and reports the validated
  number of seconds.

## [0.1.0] - 2026-10-11

Never published or tagged (commit a3b7c15).

- First version.
- `run(fn, timeout, *, args, kwargs, mode, default)` runs a callable under a
  wall-clock timeout and returns its typed result.
- Raises `CallTimeout` (a subclass of `TimeoutError`) on overrun, or returns
  `default` when one is given.
- `mode="thread"` (default) stops waiting but cannot kill a stuck,
  non-cooperative call: the thread lingers until it returns or the process exits.
- `mode="process"` truly terminates the call on overrun, at the cost of needing
  picklable arguments and result.
