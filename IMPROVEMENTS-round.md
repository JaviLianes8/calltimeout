# calltimeout improvement round

Progress:
- [x] Brainstorm ranked improvements (this file)
- [x] Validation: timeout type, NaN, infinity, TIMEOUT_MAX, zero budget, coroutine functions
- [x] Only this call's own timeout returns `default`; nested timeouts propagate
- [x] Process mode: crash detection, unpicklable results and errors, kill after a grace period, cleanup on interrupt, remote traceback
- [x] Thread mode: context variables, named threads, coroutine results
- [x] Signal mode for POSIX main threads, with nesting and swallowed timeouts
- [x] `with_timeout` decorator that keeps the signature (ParamSpec), process mode included
- [x] `CallTimeout` and `CallCrashed` pickle and copy
- [x] Contracts: typing, README examples, installed wheel e2e, POSIX run
- [x] Docs: README, CHANGELOG, docstrings, packaging metadata
- [x] Gates: ruff format, ruff check, mypy --strict, pytest
- [ ] Independent review findings fixed with regression tests
- [ ] Pull request opened, guard clean

## Starting point

`0.1.0` runs a callable in a daemon thread or a child process and raises `CallTimeout`
or returns `default`. Reading it against the standard library documentation turned up
these gaps:

- A child process that dies without a result (a crash, `os._exit`, the OOM killer) is
  reported as a timeout, and only after the whole budget has been waited out.
- A result or exception that cannot be pickled is lost in the queue's feeder thread: the
  caller waits the full budget and gets `CallTimeout`, which is the wrong error.
- On POSIX `terminate()` sends SIGTERM. A call that ignores SIGTERM makes `run` hang
  forever in `process.join()`, with the timeout already spent.
- If the waiting caller is interrupted (Ctrl+C, an outer timeout), the child process is
  never terminated.
- An exception from the child arrives without its traceback.
- `default` is returned for any `CallTimeout` raised inside the call, including one from a
  nested `run` that the outer call did not cause.
- `CallTimeout` does not survive pickling: `timeout` comes back as the message string.
- `timeout=nan` and `timeout=inf` fail with unrelated errors from `threading`, `True` is
  accepted as one second, and a coroutine function returns an unawaited coroutine.
- Thread mode drops the caller's context variables, unlike `asyncio.to_thread`.
- There is no way to interrupt pure Python code in place on POSIX (SIGALRM), and no
  decorator, so the call's arguments are never type-checked.

## Sources (fetched 2026-10-12)

- `threading`, https://docs.python.org/3/library/threading.html: `join()` always returns
  None, so `is_alive()` decides whether it timed out; daemon threads are abruptly stopped
  at shutdown and their resources may not be released.
- `signal`, https://docs.python.org/3/library/signal.html: handlers always run in the main
  thread and only the main thread may set one; a long calculation in C runs uninterrupted
  until it finishes; `setitimer(ITIMER_REAL, ...)` delivers SIGALRM, takes seconds rounded
  up to microseconds, returns the old `(delay, interval)` and is cleared by zero seconds;
  on Windows `signal()` only accepts SIGABRT, SIGFPE, SIGILL, SIGINT, SIGSEGV, SIGTERM and
  SIGBREAK; an exception from a handler may be raised after any bytecode instruction.
- `multiprocessing`, https://docs.python.org/3/library/multiprocessing.html: `terminate()`
  is SIGTERM on POSIX and TerminateProcess on Windows, skips finally clauses and orphans
  descendant processes; `kill()` is SIGKILL; `sentinel` can be waited on with
  `multiprocessing.connection.wait()`; since 3.14 the POSIX default start method is
  forkserver.
- `asyncio`, https://docs.python.org/3/library/asyncio-task.html: `asyncio.timeout(delay)`
  limits time spent waiting in a coroutine; `asyncio.to_thread` propagates the current
  `contextvars.Context` to the thread.
- PEP 475, https://peps.python.org/pep-0475/: when a system call fails with EINTR and the
  signal handler raises, the wrapper fails with that exception instead of retrying, so a
  SIGALRM handler can interrupt `time.sleep` and blocking reads.

## Ranked improvements

1. **Process mode tells a crash from a timeout.** Wait on the result pipe and the process
   sentinel together; a child that exits without a result raises `CallCrashed` with its
   exit code at once, instead of `CallTimeout` after the full budget.
2. **Process mode never hangs and never leaks.** Results and errors are pickled in the
   child before they are sent, so an unpicklable value becomes a clear error; on overrun
   the child gets `terminate()`, then `kill()` after a short grace period; a `finally`
   stops the child whenever the caller leaves early. The child's traceback is chained as
   the cause, as `concurrent.futures` does.
3. **`default` only for this call's own timeout.** A `CallTimeout` from a nested call
   propagates untouched.
4. **Strict validation.** `timeout` must be a real number (not a bool), finite, not
   negative and at most `threading.TIMEOUT_MAX`. A zero budget raises at once without
   starting the call, in every mode. Coroutine functions are rejected with a pointer to
   `asyncio.timeout`.
5. **Signal mode.** `mode="signal"` arms `ITIMER_REAL` and raises `CallTimeout` inside the
   call, which really stops pure Python code and blocking system calls in place, with no
   thread and no pickling. Main thread on POSIX only, with clear errors elsewhere. The old
   handler and any outer timer are restored with their remaining time, so nested calls
   work; a call that swallows the timeout still ends in `CallTimeout`.
6. **Thread mode like `asyncio.to_thread`.** The call runs in a copy of the caller's
   context; threads are named after the call so a leaked one is recognisable in
   `threading.enumerate()`; a call that returns a coroutine is rejected.
7. **`with_timeout` decorator.** Keeps the wrapped signature with `ParamSpec`, so the
   arguments are type-checked, and the result type becomes `T | D` with a default. It
   works in process mode for module-level functions (the child runs the original).
8. **Exceptions that travel.** `CallTimeout` and `CallCrashed` survive pickle and copy.
9. **Typed public API, proven.** A test runs mypy on a snippet and checks inferred types,
   the preserved signature, and rejection of wrong arguments.
10. **Docs with runnable examples.** Every Python block in the README runs in the test
    suite with its output pinned; a mechanism table states what each mode can and cannot
    stop on Windows and POSIX; async usage is documented.
11. **Packaging.** Classifiers for supported versions and operating systems, keywords,
    version agreement with the metadata, and an installed-wheel e2e test.

## Findings while implementing

- On Windows, a process start that fails half way through pickling its arguments (a
  lambda, say) left the next process-mode call of the same parent answering on a stale
  pipe handle: the child ran, sent its result, and the parent saw a crash with exit code
  0. Plain `multiprocessing` with a `Pipe` shows the same. Process mode now pickles the
  call into bytes before it creates the pipe or the process, so a start cannot fail half
  way (not under fork, where nothing is pickled).
- Under fork and spawn on POSIX, a grandchild forked by the call inherits both the result
  pipe and the sentinel pipe, so neither reports the child's exit while the grandchild
  lives. Waiting now also checks `is_alive()` (waitpid) every 0.25 seconds, and the grace
  period after `terminate()` is measured the same way instead of with `join(timeout)`.

## Verification

- Windows, Python 3.13 and 3.11; Linux (WSL), Python 3.14 under forkserver, fork and
  spawn. `mypy --strict --python-version 3.10` on both platforms.
- Mutations: each guard was removed in turn (pickle reducers, every validation check,
  the zero-budget shortcut, the signal-mode platform check order, context copying,
  thread names, the private expiry signal, up-front pickling, child cleanup, the rebuild
  check, the remote traceback, result pickling, the decorator's child unwrapping and
  `functools.wraps`; on Linux the waitpid fallback, the grace period, the kill, and in
  signal mode the swallowed-timeout check, the outer re-arm, passing ticks on, handler
  restore, disarming, the main-thread check and the deadline check). Every one made the
  suite fail. Passing the process sentinel to `wait` is a latency optimisation: with the
  waitpid fallback no test can fail without it.

## Out of scope

- Killing a thread: CPython has no safe way to do it. Thread mode documents the leak
  instead of hiding it.
- A start method parameter: process mode uses the platform default, which is what
  `multiprocessing` users already configure with `set_start_method`.
- Terminating grandchildren: `terminate()` orphans them by design; a call that spawns
  processes must manage them itself.
- An async API: coroutines already have `asyncio.timeout`. For blocking calls the README
  shows `asyncio.to_thread(run, ...)`.
