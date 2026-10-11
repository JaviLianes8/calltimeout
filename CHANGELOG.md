# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
