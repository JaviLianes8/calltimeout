# Earlier preparation evidence

## Baseline on 0.2.0 (before any change)

Fresh clone of `main` at 9b6975c, CPython 3.13: `ruff format --check .`, `ruff check .`
and `mypy --strict src tests` exit 0; `pytest` 86 passed, 5 skipped (POSIX-only and the
opt-in e2e tests). No doctests existed.

## API review (item 1)

Kept: `run(fn, timeout, *, args=(), kwargs=None, mode="thread", default=...)`,
`with_timeout(timeout, *, mode="thread", default=...)`, `CallTimeout` (`.timeout`),
`CallCrashed` (`.exitcode`) and `Mode`, with the same parameter names and defaults as
0.2.0. Changed, all listed in the CHANGELOG 1.0.0 section: a non-`str` mode raises
`TypeError`; the exceptions show and pickle as `calltimeout.<Name>` and keep extra
attributes and notes; a real number whose `float` conversion fails raises `TypeError`;
bounded messages; process mode counts pickling and the child's start against the budget
and never starts a call whose pickling used it up; a child that cannot load the call
reports the real error; a child that dies while sending raises `CallCrashed`; an
unpicklable result raises `pickle.PicklingError` with the child's traceback; a late
SIGALRM tick can no longer re-arm the timer; thread mode measures from the start of
`run`; the coroutine hint names `asyncio.wait_for()`. `kwargs` is copied into a plain
`dict` in the caller before the call starts (documented in the GUIDE, now pinned).

## Ground truth (item 7)

Fetched by `scripts/fetch_upstream.py` into the ignored `tests/upstream` folder on
2026-10-18 and fetched again on 2026-10-22 on two machines, sha256 matching
`tests/upstream/MANIFEST.json` each time; nothing fetched is committed or shipped.

- CPython documentation sources at tag v3.14.8 (`threading`, `signal`,
  `multiprocessing`, `asyncio-task`, `inspect`, `pickle`) and `asyncio-task` at v3.10.22,
  `https://raw.githubusercontent.com/python/cpython/<tag>/Doc/library/<name>.rst`; PEP 475
  at peps commit 6068058. `tests/test_upstream_threads.py` and
  `tests/test_upstream_processes.py` find each sentence in the fetched text, show the
  running interpreter behaves that way (join returning None, `TIMEOUT_MAX`, daemon
  threads, the context copy of `asyncio.to_thread`, negative exit codes after a signal,
  `terminate()` leaving descendants, main-thread-only handlers, a handler set outside
  Python read as `None`, a C calculation interrupted only once it returns, a raising
  handler stopping a blocking system call, the main-module guard), then that calltimeout
  follows from it.
- Real program output: pebble 5.2.3 (`https://pypi.org/project/pebble/`), installed in
  each run, executes the same seeded calls in its own process pool
  (`tests/test_oracles.py`): results, exception types and arguments, crash exit codes
  and timeouts agree. The one difference found (a worker that exits with code 0 is a crash
  here and a timeout in a pebble pool) is asserted precisely.
- The plain call `fn(*args, **kwargs)` is the oracle for every mode in
  `tests/test_fuzz_calls.py`.

## Fuzz and hostile input (item 9)

`tests/test_fuzz_arguments.py`: three seeds, each with 1,500 random timeouts (floats,
integers up to 600 digits, fractions, subnormal to huge floats, numeric-looking strings,
containers) after fixed edges (bools, NaN, infinities, `TIMEOUT_MAX` and just above it,
`Decimal`, 10**400), judged against the documented rules written independently of the
code, and 1,000 mode strings; hostile objects whose every method raises, and type names
of 100,000 characters, get a typed error of at most 300 characters; 25,000 and 100,000
keyword arguments are checked in linear time. `tests/test_fuzz_calls.py`: seeded builtin
calls with random, often invalid, arguments through thread, process and (POSIX) signal
mode give exactly the direct call's value or exception. `tests/test_hardening.py`:
messages bounded for huge integers, long type and mode names, unpicklable results and
exceptions that cannot be rebuilt.

## Packaging, e2e and Pythons (items 8, 10, 13, 14)

- Every interpreter on this PC from `requires-python` up, at 5bcc60e: the wheel and sdist
  built once from a fresh clone (the wheel byte-identical to an earlier build), the wheel
  installed in a fresh venv per interpreter and the sdist's own suite run with `src`
  removed, `CALLTIMEOUT_E2E=1` and pebble 5.2.3, plus the doctests of the installed
  package: CPython 3.10.19, 3.11.5, 3.12.12, 3.13.2, 3.14.2 and 3.14.2 free-threaded each
  167 passed, 10 skipped (POSIX only), doctests 5 passed. The one later commit only
  changes how a POSIX test patches `setitimer`.
- The e2e tests build the wheel and sdist, check their contents (package, `py.typed`,
  LICENSE, metadata; the sdist with sources, tests, docs and the manifest, without fetched
  documents or certification notes), run `twine check --strict` on both, install each in
  a throwaway venv, drive the package from an empty folder with `-I`, and type-check a
  consumer script with `mypy --strict` against the installed wheel. There is no CLI.
- POSIX: WSL Ubuntu, CPython 3.14.4, at 4106b53: format, lint and `mypy --strict src tests`
  exit 0; the suite under forkserver 194 passed, 9 skipped; fork 190 passed, 13 skipped;
  spawn 194 passed, 9 skipped (Windows-only, fork-inapplicable and opt-in e2e tests).

## Gates (item 15)

At 5bcc60e on another machine from a fresh clone (CPython 3.14, fetched documents,
pebble, `CALLTIMEOUT_E2E=1`), each on its own: `ruff format --check .`, `ruff check .`,
`mypy --strict src`, `mypy --strict src tests` exit 0, and `pytest` 171 passed, 13
skipped (POSIX only), exit 0. At 4106b53 the static gates exit 0 again on this PC
(mypy for the Windows, Linux and macOS platforms) and the full gate under WSL (above).
At 3220523 the static gates exit 0 on this PC and under WSL, and `pytest` passes on every
interpreter as the round 6 verification below records (the full suite at f477ccf, the two
files changed since rerun at 3220523).
At 05d15a6 the static gates exit 0 on this PC and under WSL, and `pytest` passes on every
Windows interpreter and under each Linux start method, as the round 7 verification records.
At e2db93d the gates, `pytest` included, exit 0 on Elena's PC (CPython 3.14.2), and at
be35644 the static gates exit 0 on this PC, as the round 8 verification records.

