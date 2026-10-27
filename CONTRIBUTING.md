# Contributing

Thanks for taking the time. This project keeps a small, predictable shape.

## Setup

```
pip install -r requirements-dev.txt
```

## Before you open a pull request

- Keep public API in `src/calltimeout/__init__.py`; internals live in `_`-prefixed modules.
- Add a test for the behaviour you change. The library's promise is about real time, so
  the suite measures real budgets with real threads, child processes and timers. Tests
  use no network (sockets only as local pairs handed to a child), and write files only
  under pytest's `tmp_path`.
- Run `scripts/check.ps1` (format, lint, types, tests) and make sure it passes.
- One logical change per commit, imperative subject line.

Open an issue first if the change is large or shifts the public API.
