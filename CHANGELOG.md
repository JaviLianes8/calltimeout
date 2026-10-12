# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0]

### Added

- `mode="signal"`: a SIGALRM timer raises `CallTimeout` inside the call, which stops
  pure Python code and blocking system calls in place. POSIX main thread only; other
  threads get `RuntimeError` and Windows `NotImplementedError`. Timers already armed
  keep their schedule, so calls can be nested, and a call that swallows the timeout
  still ends in `CallTimeout`.
- `with_timeout(timeout, *, mode, default)`: a decorator that keeps the wrapped
  function's signature for type checkers (`ParamSpec`), in every mode including process
  mode for module-level functions.
- `CallCrashed`: raised in process mode when the child exits without a result, with its
  exit code, as soon as it is gone.

### Changed

- Process mode waits on the result pipe and the process together, pickles results and
  errors in the child (an unpicklable result raises `pickle.PicklingError` at once, an
  unpicklable exception arrives as a `RuntimeError` stand-in), chains the child's
  traceback as the cause, kills a child that ignores SIGTERM after 1 second, and stops
  the child whenever the caller leaves early, including on `KeyboardInterrupt`.
- Process mode pickles the call before starting the child, so a failed start cannot
  leave the next call reading from a stale pipe on Windows.
- `default` is returned only for the call's own timeout; a `CallTimeout` from a nested
  call propagates.
- Thread mode runs the call in a copy of the caller's context variables and names the
  thread `calltimeout:<function>`.
- `timeout` must be a real number (not a bool), not NaN and at most
  `threading.TIMEOUT_MAX`; a zero timeout raises without starting the call. Coroutine
  functions and coroutine results are rejected with a pointer to `asyncio.timeout`.
- `CallTimeout` keeps its `timeout` through pickle and copy.

## [0.1.0]

- First release.
- `run(fn, timeout, *, args, kwargs, mode, default)` runs a callable under a
  wall-clock timeout and returns its typed result.
- Raises `CallTimeout` (a subclass of `TimeoutError`) on overrun, or returns
  `default` when one is given.
- `mode="thread"` (default) stops waiting but cannot kill a stuck,
  non-cooperative call: the thread lingers until it returns or the process exits.
- `mode="process"` truly terminates the call on overrun, at the cost of needing
  picklable arguments and result.
