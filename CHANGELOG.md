# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.0] - 2026-10-26

The public API is now stable: `run`, `with_timeout`, `CallTimeout`, `CallCrashed`,
`RemoteTraceback` and `Mode`, with their parameter names, defaults and exception types,
follow Semantic Versioning from this release on. calltimeout was never published before 1.0.0, and
0.1.0 and 0.2.0 were never tagged; the changes below are against 0.2.0, commit 9b6975c
on `main`.

### Added

- `RemoteTraceback`, the cause chained to an exception raised by a process-mode call,
  whose text (`.text`) is the child's traceback, is public and shown and pickled as
  `calltimeout.RemoteTraceback`. It was a private class, shown in every such traceback
  as `calltimeout._wire.RemoteTraceback`.

### Changed

- A `mode` that is not a `str` raises `TypeError` (it raised `ValueError`); an unknown
  mode name still raises `ValueError`, and the message lists the three valid names. A
  `str` subclass is read as the plain name.
- `CallTimeout` and `CallCrashed` are shown and pickled as `calltimeout.CallTimeout` and
  `calltimeout.CallCrashed`, so a pickle never names a private module, and they keep
  extra attributes (such as notes) through pickle and copy.
- A real-number timeout whose conversion to `float` fails raises `TypeError` (the
  conversion's own error is chained as the cause).
- A negative timeout too large for a `float` (`-10**400`) raises "timeout must not be
  negative"; it was reported as above `threading.TIMEOUT_MAX`.
- Error messages are bounded: a quoted value or name is cut after 60 characters, a
  quoted exception after 300 (60 for pickle's error about a call or a result that cannot
  be sent, or a result that cannot be rebuilt, which can quote an argument or the
  result), and an integer of more than 64 bits is described by its size instead of
  printed.
  A name or text that is a `str` subclass is measured as a plain `str`, so one that lies
  about its length is cut too (a type or function name of a million characters went whole
  into argument errors, the coroutine error, thread and process names, and the
  `RuntimeError` standing in for a child's unpicklable error). A type whose name lookup
  raises, or gives something other than text, is named `<unnamed type>` (or
  `<unnamed callable>`) instead of that error escaping from `run`.
- `kwargs` is read once into a plain `dict` in the caller, before the call starts, and its
  keys are checked on that copy, so the call gets exactly the keys that were checked. A
  mapping whose iteration hides keys that `keys()` returns, or one that changes between
  reads, got past the check and failed inside the call (in process mode, after a child
  had started) with a `TypeError` from Python itself.
- Process mode: the budget also covers pickling the call and starting the child, and a
  call whose pickling used it up is never started. A child that cannot load the call
  (a function the child cannot import under spawn or forkserver) reports that error
  with its traceback instead of a crash with exit code 1. A child that dies while
  sending its result raises `CallCrashed`, and waiting for a crashed child's exit code
  never runs past the budget. A result that cannot be pickled raises
  `pickle.PicklingError` with the child's traceback of the failure, and a result that
  cannot be rebuilt raises `pickle.UnpicklingError`; pickle's error behind either is
  bounded as for a call that cannot be sent (below), in the child's traceback text for a
  result that cannot be sent back. It was chained whole: a result nested 50,000 lists
  deep sent back a traceback of over a million characters on Python 3.14, and an
  argument with thousands of huge notes, returned as the result under fork, spent the
  whole budget formatting it and ended in `CallTimeout`. The `UnpicklingError` of a
  result whose class the caller cannot import is now chained from a `RuntimeError` naming
  `ModuleNotFoundError`.
- Process mode: a call whose function or arguments cannot be pickled raises
  `pickle.PicklingError` before any process starts, chained from pickle's own error
  (which was raised as it was, a different type on each Python version). That error is
  bounded: its text is cut after 300 characters, and only its first ten notes are kept,
  each cut after 60 characters, followed by a count of the rest. The plain errors pickle
  raises (`TypeError`, `ValueError`, `RuntimeError`, `pickle.PicklingError` and a few
  more, exactly those types) are cut in place; any other (an argument's `__reduce__` can
  raise a subclass, an error with a `__str__` of its own, a type that cannot be named) is
  replaced as the cause by a `RuntimeError` naming its type and quoting its text, read
  once. Errors chained to it are not kept, since they can quote the argument too. A call
  holding objects that `multiprocessing` only pickles while a child starts (locks,
  queues, shared values), any number of them, is first rehearsed as the start will
  pickle it, so one whose contents cannot pickle (a `Value` guarded by a
  `threading.Lock`) fails the same way, and one that still fails when the start pickles
  it again (an object that pickles only once, a manager proxy whose pickling raises)
  raises the same error, its child
  stopped before it runs anything; a `KeyboardInterrupt` or `SystemExit` raised there is
  raised as it is, once that child is stopped, instead of escaping half way through the
  start, which on Windows could break later calls passing pipe ends. Under forkserver, a
  call holding more than 248 descriptors (pipe ends, sockets, two per queue, one per block
  of shared memory behind `Value` and `Array` objects, all named in the message), more than
  one message to the fork server carries, raises `pickle.PicklingError` before any
  process starts instead of an undocumented `OSError` or `ValueError` from the start. An
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
- Process mode frees the child's handles as soon as the call ends. A call that raised
  kept its child's process object, and its two descriptors or handles, alive in a
  reference cycle until the next garbage collection, so a loop of failing calls could
  run out of file descriptors (`OSError: [Errno 24] Too many open files`).
- `with_timeout` in process mode sends a callable that pickles by value (a
  `functools.partial`, a callable object) as it is, as `run` does; it failed with
  `AttributeError` under spawn and forkserver.
- `with_timeout` in process mode works under a `classmethod` under spawn and forkserver
  (the wrapper is sent through its class); it raised `pickle.PicklingError`.
- Process mode: a child error whose type's own attributes raise (its traceback cannot be
  formatted, its type cannot be named or pickled) arrives as a `RuntimeError` quoting its
  text; the child crashed with exit code 1 and `run` raised `CallCrashed`.
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
- Signal mode: an interval timer that was already running keeps its own schedule. Each
  tick due during a call was counted from when it ran instead of when it was due, so up
  to 1 ms of lateness per tick added up and ticks were lost (400 calls of 5 ms under a
  10 ms timer: about 10 ticks lost, the last 120 to 130 ms late). On Linux a timer read
  in the instant between a tick and its delivery shows no time left, and the call then
  left it disarmed for good; it is now kept.
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
