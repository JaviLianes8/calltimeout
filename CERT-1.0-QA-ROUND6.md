# QA findings and verification

### Round 6, at 7661bda

The five lenses again, each with fresh agents. Lens a ran every doctest and documented
example on Windows spawn and Linux fork, spawn and forkserver, and 85 to 90 documented
claims per start method, all passing; lens b re-derived exit codes, deadlines, the
forkserver descriptor limit and the signal rules from CPython sources and the kernel;
lens d built the wheel and sdist twice (byte-identical), installed them on CPython 3.10.19
to 3.14.2 and upgraded from 0.2.0; lens e ran 99 mutants of its own (93 killed, 1
equivalent). Every finding is fixed in f477ccf (two of its new contracts corrected in 3220523, below); each behaviour fix has a contract that
fails on 7661bda and passes now, and every behaviour change is in the CHANGELOG.

| Lens | Id | Severity | Finding | Fix | Contract |
| --- | --- | --- | --- | --- | --- |
| c | F1 | medium | The errors about a result were not bounded like those about a call: the message quoted 300 characters of pickle's error, which was chained whole (text, notes, chain) into the child's traceback; a result nested 50,000 deep sent back over a million characters on 3.14, and thousands of huge notes, under fork, spent the whole budget formatting | `_wire._about` builds all three documented errors (call not sent, result not sent back, result not rebuilt): pickle's error goes through `bounded` (300 characters, ten notes of 60, nothing chained), the message quotes 60, and the error is raised outside the handler so the original is not its context | `test_result_bounds.py` (a 200,000-character error, 2,000 notes of 5,000 characters, a huge chained context, a 50,000-deep list, a result whose rebuild raises 200,000 characters: message, context and the whole printed chain bounded); `test_bounded_causes.py` now expects 60 quoted characters and the 300-character cut in the child's text |
| c | F2 | low | The key check iterated the mapping while the call read `dict(kwargs)`, so a mapping whose views disagree (or that changes between reads) passed with a non-`str` key, and the `TypeError` came from inside the call, after a child had started in process mode | `check_call` copies `kwargs` once into a `dict`, checks the keys of that copy and returns it; `run` passes the same copy to the runner | `test_contract_edges.py::test_the_kwargs_checked_are_the_kwargs_the_call_gets` (every mode: a `dict` subclass hiding a key from iteration is refused with our message, no cause and no process started; a mapping that adds a key on its second pass is read once and called with what was checked) |
| a | A1, A2 | low | Two GUIDE examples failed `mypy --strict` (`inner() -> str` returning `None`, `main() -> str` returning `str \| None`) | Annotated `-> None` and `-> str \| None` | `test_typing.py::test_every_documented_example_passes_strict_type_checking` (all seven README and GUIDE blocks, for win32 and linux) |
| b | F1 | low | The GUIDE promised the grace period lets atexit handlers run, which fork and forkserver children only do from Python 3.13 | GUIDE and the `_stop` docstring: atexit handlers run where `multiprocessing` runs them (spawn, and fork and forkserver from 3.13) | `test_process.py::test_the_calls_atexit_handlers_run_where_multiprocessing_runs_them` (skipped where they do not run) |
| d | D1 | low | README (mode table and API note) and the `run` docstring said `fn` and its arguments always pickle; under fork only the result does | Both qualified by start method | docs |
| c | F3 | low | The GUIDE said the budget covers pickling, without saying pickling runs in the caller and cannot be interrupted | GUIDE, `run` and `run_in_process` docstrings | docs |
| c | F4 | low | Only resetting `ITIMER_REAL` was documented as cancelling a signal-mode deadline; installing a `SIGALRM` handler (or `SIG_IGN`) does too, and the result is then returned | Documented next to the `ITIMER_REAL` rule | docs |
| e | S09 | high | Restoring an enclosing timer that fell due as `max(left, 0.0)` (which disarms it) survived | | `test_signal_restore.py`: an enclosing one-shot timer that fell due while the call overran still fires once, and a periodic one stays armed with its interval |
| e | T03 | medium | Thread mode waiting 0.5 s past the budget survived | | `test_timing_contracts.py::test_thread_mode_raises_within_a_small_margin_of_the_budget` (best of three under budget + 0.1 s) |
| e | P10 | medium | Process mode sleeping a whole poll interval past the deadline survived | | `test_process_mode_never_sleeps_past_the_deadline` (poll interval raised to 20 s, the timeout still comes before the grace period ends) |
| e | P08 | low | A result sent as the child exits, seen only through the sentinel, was untested | | `test_a_result_sent_as_the_child_exits_is_returned` (the first wait returns nothing after the child exited) |
| e | X05 | low | The fallback for a number that cannot be printed was untested | | `test_errors.py::test_a_number_that_cannot_be_printed_is_named_by_its_type` |

Also changed: the `UnpicklingError` of a result whose class the caller cannot import is
chained from a `RuntimeError` naming `ModuleNotFoundError` (bounded like any non-plain
error), and `test_regressions.py` says so.

Observations the lenses reported outside their findings, left as they are: the README
link to `blob/main/GUIDE.md` answers 404 until `release/1.0.0` is merged (lenses a and d);
under fork, a thread-mode call left running makes later process calls fork a
multi-threaded process, which CPython warns about (lens d); `CallCrashed.exitcode` is the
value `multiprocessing` reports, truncated by the OS like any exit status (lens b).

Verification:

- WSL Ubuntu, CPython 3.14.4, fresh clone of f477ccf: `ruff format --check .`,
  `ruff check .`, `mypy --strict src` and `mypy --strict src tests` exit 0. `pytest` under
  forkserver, fork and spawn: everything passed but
  `test_the_notes_of_an_error_about_a_result_are_bounded_and_counted`, which expected
  1,990 dropped notes where 3.14 has 1,991: pickle 3.14 adds a note of its own (which
  tuple item failed) to the 2,000 of the error. The new contracts run on the src of
  7661bda: the five of `test_result_bounds.py` and the three of
  `test_the_kwargs_checked_are_the_kwargs_the_call_gets` fail, the others pass (they pin
  behaviour 7661bda already had, against lens e's mutants). Lens e's survivors S09, T03,
  P10, P08 and X05, each applied alone to f477ccf: all killed.
- Windows, this PC, fresh clone of f477ccf from GitHub: the wheel and sdist built once and
  installed per interpreter, the sdist's own suite run with `src` removed,
  `CALLTIMEOUT_E2E=1`, the fetched documents and pebble 5.2.3, plus the installed
  package's doctests (5 passed on each). CPython 3.11.5 and 3.13.2 each 324 passed, 22
  skipped. Two contracts were wrong, not the library: on 3.10.19 the notes contract failed
  because `traceback` prints notes only from 3.11 (the same skip the other notes tests
  have); on 3.14.2 and 3.14.2 free-threaded it failed as on Linux; on 3.12.12 the thread
  timing contract measured 0.187 s for a 0.2 s budget, because `time.monotonic()` there
  is `GetTickCount64()` with a resolution of 0.015625 s (`time.get_clock_info` on this PC:
  3.10.19, 3.11.5 and 3.12.12 report `GetTickCount64()`, 3.13.2 and 3.14.2
  `QueryPerformanceCounter()` at 1e-07 s).
- 3220523 corrects both: the notes contract skips before 3.11 and expects the number of
  notes pickle itself leaves on this interpreter (2,000 or 2,001) minus the ten kept; the
  timing contract allows one tick of the clock below the budget. The GUIDE says that
  thread and process mode are as precise as `time.monotonic()`, and what it is on
  Windows. Both files rerun at 3220523: on Windows with CPython 3.10.19 (7 passed, 1
  skipped), 3.11.5, 3.12.12, 3.13.2, 3.14.2 and 3.14.2 free-threaded (8 passed each); on
  WSL under forkserver, fork and spawn (8 passed each); on the src of 7661bda the five
  contracts of `test_result_bounds.py` still fail; T03 still killed.
- The gates on this PC at 3220523 (CPython 3.13.2, ruff 0.17.0, mypy 2.4.0): all exit 0.

