# calltimeout 1.0.0 certification report

The 1.0.0 certification bar (19 items) applied to calltimeout. No release is on PyPI
(`https://pypi.org/pypi/calltimeout/json` answered 404 on 2026-10-18, 2026-10-22 and
2026-10-25), so there is no upgrade path to test; the changes below are listed against
0.2.0, the last state of `main` before this branch (9b6975c, never tagged).

Progress:
- [x] Branch `release/1.0.0` created from `main` (9b6975c, 0.2.0)
- [x] Baseline gates on 0.2.0
- [x] API review and 1.0.0 changes (item 1)
- [x] Errors, typing, docstrings and doctests (items 2 to 5)
- [x] Ground truth: documentation fetched live, pebble run live (item 7)
- [x] Contract, fuzz and author mutation round (items 6, 9, 18)
- [x] Docs: README, GUIDE, CHANGELOG (items 11, 12)
- [x] Packaging, e2e, every Python (items 8, 10, 13, 14)
- [x] Gates (item 15)
- [x] PR and trace guard
- [x] Five QA lenses, round 1: every finding fixed (3309979)
- [x] Five QA lenses, round 2: every finding fixed (00f6889, 6e2c03c)
- [x] Five QA lenses, round 3: every finding fixed (2f962f3 to db26ef1)
- [x] Five QA lenses, round 4: every finding fixed (726f948 to 388e62b)
- [x] Lens e, round 5: every surviving mutant pinned or shown equivalent (9f00374, 5b84b46)
- [x] Five QA lenses, round 6: every finding fixed (f477ccf, 3220523)
- [ ] Five QA lenses re-verified (item 19) and independent reviewer (item 16)

## Scorecard

| # | Item | Result |
| --- | --- | --- |
| 1 | Public API reviewed for stability | PASS: the five names of 0.2.0 kept with their parameter names and defaults, pinned by `tests/test_contract_api.py`; every behaviour change in the CHANGELOG and the GUIDE |
| 2 | `__all__` exact, no private imports in docs | PASS: `CallCrashed`, `CallTimeout`, `Mode`, `run`, `with_timeout`; `tests/test_contract.py` |
| 3 | Docstrings with runnable examples, doctests | PASS: every public name has a doctest (5, also run from the installed wheel; `Mode`'s section of the package docstring is run by `tests/test_contract.py`, since a docstring on the cached `Literal` would relabel the caller's identical aliases); README and GUIDE examples run as scripts by the tests with their printed output checked |
| 4 | Typed end to end | PASS: `mypy --strict src tests` for the Windows, Linux and macOS platforms; `py.typed` shipped; a consumer script type-checked against the installed wheel |
| 5 | Typed, documented, bounded errors | PASS: `CallTimeout` (`TimeoutError`), `CallCrashed` (`RuntimeError`), `TypeError` or `ValueError` before the call starts; quoted values cut at 60 characters, exceptions at 300 (60 in the message for a call or a result that cannot be sent or rebuilt, whose chained pickle error is cut at 300 in place), huge integers described by size |
| 6 | Contract tests of every public name | PASS |
| 7 | Real ground truth | PASS: 8 CPython and PEP documents fetched with a hash manifest, each fact checked against the running interpreter; pebble 5.2.3 run live as a second implementation |
| 8 | Real e2e from the wheel | PASS: wheel and sdist built, inspected, installed in throwaway venvs and used from an empty folder; no CLI; nothing on PyPI to upgrade from |
| 9 | Seeded fuzz, no crash, hang or blowup | PASS |
| 10 | Supported Pythons | PASS: CPython 3.10.19, 3.11.5, 3.12.12, 3.13.2, 3.14.2, 3.14.2 free-threaded (Windows) and 3.14.4 (Linux, three start methods); 3.8 and 3.9 are below `requires-python` |
| 11 | README and `twine check` | PASS: `twine check --strict` in the e2e tests, absolute links, problem, why versus five alternatives checked on PyPI on 2026-10-22, certified badge |
| 12 | Dated CHANGELOG section | PASS: `## [1.0.0] - 2026-10-25` |
| 13 | pyproject 1.0.0, Production/Stable | PASS: 3.10 to 3.14, CPython, MIT, Homepage/Source/Issues/Changelog, keywords, `dependencies = []` |
| 14 | sdist and wheel contents | PASS: asserted by `tests/test_e2e_wheel.py` |
| 15 | Gates each exit 0 | PASS: see Gates |
| 16 | Independent reviewer | pending |
| 17 | PR and trace guard | PR #3 from `release/1.0.0`, trace guard CLEAN; merge and publish left to the maintainer |
| 18 | Contracts bite (mutations) | PASS: 58 author mutants, 57 killed; M36 killed under fork and spawn and unreachable under forkserver |
| 19 | Five independent QA lenses | Rounds 1 to 4: every finding of the five lenses fixed, at 3309979, at 00f6889 and 6e2c03c, at 2f962f3 to db26ef1, and at 726f948 to 388e62b; round 5: lens e's survivors pinned in 9f00374 and 5b84b46; round 6: every finding fixed in f477ccf and 3220523 (see QA lenses); re-verification pending |

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

## Author mutation round (item 18)

58 mutants (`scripts/mutants.json`) over every module, each applied alone by
`scripts/mutate.py` to a fresh clone of the pushed branch, the full suite (fetched
documents and pebble present) run with `-x` and a 300 s per-test limit; every process a
mutant leaves behind, orphans included, is ended before the next one. Windows mutants ran
on another machine (CPython 3.14) at 6656871; the POSIX ones (marked in the JSON) under
WSL Ubuntu, CPython 3.14.4. Eight survived the first pass (M23, M26, M31, M34, M47, M48,
M56, M57); the missing contracts were added in cd9e60e and a4d7354 and all eight were
killed at a4d7354. M33 to M36 and M47 to M58 were run again at 4106b53 under forkserver.
M36 removes the `is_alive()` fallback for a grandchild that inherits the result pipe and,
under fork and spawn, the sentinel: killed under both. Under forkserver the sentinel is
not inherited, the child's exit is seen through it and the branch is never reached, so
the mutant is equivalent there.

| Id | Mutation | File | Result | Caught by |
| --- | --- | --- | --- | --- |
| M01 | a bool timeout accepted | `_validate.py` | killed | `test_fuzz_arguments.py::test_every_timeout_is_judged_by_the_documented_rules[1]` |
| M02 | negative check off by one | `_validate.py` | killed | `test_fuzz_arguments.py::test_every_timeout_is_judged_by_the_documented_rules[1]` |
| M03 | TIMEOUT_MAX itself refused | `_validate.py` | killed | `test_fuzz_arguments.py::test_every_timeout_is_judged_by_the_documented_rules[1]` |
| M04 | NaN check dropped | `_validate.py` | killed | `test_validation.py::test_the_decorator_rejects_bad_settings_when_applied[<lambda>1]` |
| M05 | -0.0 kept negative | `_validate.py` | killed | `test_regressions.py::test_the_timeout_is_reported_as_the_validated_float` |
| M06 | coroutine function check dropped | `_validate.py` | killed | `test_upstream_threads.py::test_a_partial_of_a_coroutine_function_is_refused_without_its_arguments` |
| M07 | a list accepted as args | `_validate.py` | killed | `test_validation.py::test_rejects_args_that_are_not_a_tuple` |
| M08 | kwargs key check dropped | `_validate.py` | killed | `test_validation.py::test_rejects_kwargs_with_keys_that_are_not_strings` |
| M09 | str subclass mode used as given | `_validate.py` | killed | `test_hardening.py::test_a_str_subclass_mode_is_read_as_the_plain_name` |
| M10 | wrong error type for a non-str mode | `_validate.py` | killed | `test_fuzz_arguments.py::test_only_the_three_mode_names_are_accepted[1]` |
| M11 | coroutine result not closed | `_validate.py` | killed | `test_validation.py::test_rejects_a_coroutine_returned_by_the_call[thread]` |
| M12 | float conversion failure leaks | `_validate.py` | killed | `test_fuzz_arguments.py::test_hostile_arguments_still_get_a_short_typed_error` |
| M13 | cut keeps one character more | `_text.py` | killed | `test_hardening.py::test_an_unknown_mode_is_quoted_briefly_and_the_names_are_listed` |
| M14 | huge integer boundary off by one | `_text.py` | killed | `test_hardening.py::test_a_huge_integer_is_described_not_printed` |
| M15 | call name fallback lost | `_text.py` | killed | `test_upstream_threads.py::test_a_partial_of_a_coroutine_function_is_refused_without_its_arguments` |
| M16 | CallTimeout pickles without its state | `_errors.py` | killed | `test_hardening.py::test_extra_attributes_and_notes_survive_pickle[error0]` |
| M17 | CallCrashed prints a huge exit code | `_errors.py` | killed | `test_hardening.py::test_a_huge_integer_is_described_not_printed` |
| M18 | CallTimeout keeps its private module | `__init__.py` | killed | `test_contract_api.py::test_public_objects_live_under_the_package_name` |
| M19 | zero budget starts the call | `_api.py` | killed | `test_fuzz_arguments.py::test_only_the_three_mode_names_are_accepted[1]` |
| M20 | default and raise swapped | `_api.py` | killed | `_api.py::calltimeout._api.run` (doctest) |
| M21 | timeout reported as given | `_api.py` | killed | `test_regressions.py::test_the_timeout_is_reported_as_the_validated_float` |
| M22 | signal mode check after the zero shortcut | `_api.py` | killed | `test_signal_windows.py::test_the_platform_error_comes_before_the_zero_budget_shortcut` |
| M23 | kwargs passed through uncopied | `_api.py` | survived, then killed | `test_contract_edges.py::test_kwargs_are_read_once_in_the_caller_before_the_call_starts[thread]` |
| M24 | context variables not copied | `_thread.py` | killed | `test_thread.py::test_the_call_sees_the_callers_context_variables` |
| M25 | worker is not a daemon | `_thread.py` | killed | `test_thread.py::test_a_lingering_call_runs_in_a_named_daemon_thread` |
| M26 | thread wait twice the budget | `_thread.py` | survived, then killed | `test_contract_edges.py::test_an_overrun_ends_after_the_budget_and_well_before_twice_it[thread]` |
| M27 | coroutine result returned | `_thread.py` | killed | `test_validation.py::test_rejects_a_coroutine_returned_by_the_call[thread]` |
| M28 | thread name loses the call | `_thread.py` | killed | `test_thread.py::test_a_lingering_call_runs_in_a_named_daemon_thread` |
| M29 | no grace period for a finished child | `_process.py` | killed | `test_docs.py::test_the_grace_period_in_the_docs_matches_the_code` |
| M30 | a broken pipe escapes as OSError | `_process.py` | killed | `test_hardening.py::test_a_reader_cut_short_counts_as_no_result` |
| M31 | pickling past the budget still starts | `_process.py` | survived, then killed | `test_contract_edges.py::test_a_call_whose_pickling_spends_the_budget_starts_no_process` |
| M32 | a lost child is waited for without limit | `_process.py` | killed | `test_hardening.py::test_waiting_for_a_lost_childs_exit_stays_within_the_budget` |
| M33 | a child ignoring SIGTERM is never killed | `_process.py` | killed (POSIX) | `test_process.py::test_a_child_that_ignores_sigterm_is_killed` |
| M34 | the child target is not claimed once | `_process.py` | survived, then killed | `test_contract_edges.py::test_a_decorated_process_function_called_inside_its_own_child_gets_a_new_child` |
| M35 | the child does not mark its target | `_process.py` | killed | `test_contract_edges.py::test_a_decorated_process_function_called_inside_its_own_child_gets_a_new_child` |
| M36 | a crash behind a grandchild goes unseen | `_process.py` | killed under fork and spawn; equivalent under forkserver | `test_process.py::test_a_crash_is_seen_even_while_a_grandchild_holds_the_pipe` |
| M37 | a crash reports the wrong exit code | `_process.py` | killed | `test_docs.py::test_every_example_runs_and_prints_what_its_comments_say[GUIDE.md-5]` |
| M38 | a load failure in the child is a crash | `_process.py` | killed | `_api.py::calltimeout._api.run` (doctest) |
| M39 | an exception that cannot be rebuilt is sent | `_wire.py` | killed | `test_process.py::test_an_exception_that_cannot_be_rebuilt_arrives_as_a_stand_in` |
| M40 | the child traceback is not chained | `_wire.py` | killed | `test_docs.py::test_every_example_runs_and_prints_what_its_comments_say[GUIDE.md-5]` |
| M41 | detail cut too short | `_wire.py` | killed | `test_hardening.py::test_an_unpicklable_result_carries_the_childs_traceback_of_the_failure` |
| M42 | a result pickling failure is not chained | `_wire.py` | killed | `test_hardening.py::test_an_unpicklable_result_carries_the_childs_traceback_of_the_failure` |
| M43 | the wrapper is always sent to the child | `_decorator.py` | killed | `test_regressions.py::test_the_decorator_works_when_assigned_to_another_name` |
| M44 | metadata of the function not kept | `_decorator.py` | killed | `test_decorator.py::test_metadata_of_the_wrapped_function_is_kept` |
| M45 | the decorator ignores its default | `_decorator.py` | killed | `_decorator.py::calltimeout._decorator.with_timeout` (doctest) |
| M46 | the decorator does not check the function | `_decorator.py` | killed | `test_validation.py::test_the_decorator_rejects_a_coroutine_function` |
| M47 | re-arm delay of zero disarms | `_signal.py` | survived, then killed | `test_signal_edges.py::test_a_handler_that_overruns_the_deadline_still_ends_the_call` |
| M48 | a late tick re-arms the timer | `_signal.py` | survived, then killed | `test_signal_edges.py::test_a_tick_pending_at_the_disarm_does_not_arm_the_timer_again` |
| M49 | any exception after the alarm counts as the timeout | `_signal.py` | killed | `test_signal_posix.py::test_keyboard_interrupt_after_a_swallowed_timeout_propagates` |
| M50 | KeyboardInterrupt read as the timeout | `_signal.py` | killed | `test_signal_posix.py::test_keyboard_interrupt_after_a_swallowed_timeout_propagates` |
| M51 | previous handler not restored | `_signal.py` | killed | `test_signal_posix.py::test_returns_the_default_and_restores_the_previous_handler` |
| M52 | outer timer not restored | `_signal.py` | killed | `test_signal_posix.py::test_an_enclosing_timer_keeps_its_schedule` |
| M53 | a swallowed timeout returns normally | `_signal.py` | killed | `test_signal_posix.py::test_a_swallowed_timeout_still_ends_in_call_timeout` |
| M54 | signal mode allowed off the main thread | `_signal.py` | killed | `test_signal_posix.py::test_refuses_to_run_outside_the_main_thread` |
| M55 | a periodic outer timer becomes one-shot | `_signal.py` | killed | `test_signal_posix.py::test_a_periodic_outer_timer_is_not_starved` |
| M56 | an early wake is not re-armed | `_signal.py` | survived, then killed | `test_signal_edges.py::test_a_tick_before_the_deadline_by_the_clock_arms_the_rest` |
| M57 | outer tick passed on twice | `_signal.py` | survived, then killed | `test_signal_edges.py::test_a_stray_signal_once_the_outer_timer_is_due_passes_it_on_once` |
| M58 | handler set outside Python accepted | `_signal.py` | killed | `test_signal_posix.py::test_a_handler_set_outside_python_is_refused` |

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

## QA lenses (item 19)

### Round 1, at 204448f

Five independent lenses (a: API and docs, b: correctness and ground truth, c: adversarial,
d: packaging and e2e, e: contract strength with its own 64 mutants). Every finding was
fixed in 3309979; each behaviour fix has a contract that failed on 204448f (Windows
CPython 3.13.2 and WSL CPython 3.14.4) and passes on 3309979.

| Lens | Id | Severity | Finding | Fix | Contract |
| --- | --- | --- | --- | --- | --- |
| c | F1 | high | Windows: an argument whose pickling raised a `RuntimeError` subclass (a pool, a deep nesting, a reduce raising) was passed on to `Process.start()`, failed after the child was created and broke the next call | `prepickle` leaves to the start only the objects `multiprocessing.context.assert_spawning` refuses, after a dry run proves the rest of the call pickles; anything else raises before any process exists | `test_sending_calls.py`: five bad arguments and a pool, each followed by good calls, no process started |
| b, c, d | b F3, c F2, d F2 | low | An unpicklable `fn` or argument raised pickle's own error, a different type per Python version, undocumented, with 3.14 notes quoting a whole dict key | One documented `pickle.PicklingError` ("the call cannot be sent to the child process: ...") chained from pickle's error, its notes bounded to ten of 60 characters; README, GUIDE errors table and `run` docstring | `test_an_unpicklable_function_raises_the_same_error_on_every_python`, `test_pickles_notes_quoting_a_huge_key_are_bounded`, `test_process.py::test_an_unpicklable_callable_fails_before_waiting` |
| c | F2 (part) | low | `with_timeout(mode="process")` on a `functools.partial` or a callable object failed with `AttributeError` under spawn and forkserver | The original is sent whenever the wrapper cannot be found by name | `test_the_decorator_sends_a_callable_that_pickles_by_value` |
| b | F1 | medium | Signal mode: `raise E from other` inside `except CallTimeout` escaped as `E` | `_caused_by` follows both `__cause__` and `__context__` | `test_signal_edges.py::test_an_error_raised_from_another_cause_while_handling_the_timeout_counts_as_it` |
| d, e | d F1, e F7 | medium | Signal mode: a re-arm of a few microseconds could fire before the interrupted call blocked again, so the call overran by its whole sleep; the half-speed clock test was flaky | A tick less than 1 ms before the deadline ends the call, and the handler never re-arms for less than 1 ms; GUIDE and CHANGELOG | `test_the_handler_never_re_arms_for_less_than_a_millisecond`, `test_an_outer_tick_just_before_the_deadline_ends_the_call` |
| c | F3 | low | A callable whose `__getattr__` raises something other than `AttributeError` was refused with that error | The coroutine probe treats its failure as "not a coroutine function"; the decorator copies only the metadata it can read | `test_messages.py::test_a_callable_whose_getattr_raises_something_else_still_runs` |
| a | F1 | medium | The process-mode examples had no main guard and crashed when run as scripts under spawn and forkserver; the docs test hid it with `exec` | README block 2 and GUIDE blocks 2 and 5 guarded; `test_docs.py` runs every block as `python example.py` | `test_every_example_runs_as_a_script_and_prints_what_its_comments_say`, `test_every_process_example_guards_its_entry_point` |
| a, d | a F2, d F2 | low | The CHANGELOG said 0.2.0 was tagged; no tag exists and the old entries had no date | Reworded (commit 9b6975c, never tagged or published); 0.2.0 and 0.1.0 dated by their commits | |
| a | F3 | low | `timeout: float` rejected a `Fraction` under mypy although the docs accept it | `timeout: float \| numbers.Real` in `run`, its overloads and `with_timeout` | `test_typing.py`, snippet lines 18 and 19 |
| a | F4 | low | `Mode` had no docstring of its own | `Mode.__doc__` with a runnable example | `test_contract.py::test_mode_has_its_own_docstring_with_an_example_that_runs` |
| a, b | a F5, b F2 | low | README said process mode does not share context variables; under fork the child sees a copy | Cell reworded: a copy under fork, the defaults under spawn and forkserver, changes never come back | |
| a | F6 | low | The decorator docs said every setting is checked when it is made; signal mode's platform and thread checks run per call | Sentence added to the GUIDE and the docstring | |
| e | X3 | medium | Only a test that needs the fetched documents pinned that a partial is named without its bound arguments | | `test_a_partial_is_named_by_its_type_never_by_its_bound_arguments` |
| e | S7 | medium | Nothing pinned that an enclosing timer with the default action still ends the process | | `test_an_enclosing_timer_with_the_default_action_still_ends_the_process` (subprocess, exit `-SIGALRM`) |
| e | W5 | low | The 300-character cut of a quoted exception was untested | | `test_an_unpicklable_result_with_a_huge_error_gets_a_bounded_message`, `test_an_unrebuildable_result_with_a_huge_error_gets_a_bounded_message` |
| e | X1 | low | The 60-character boundary was not pinned | | `test_a_quoted_value_of_exactly_60_characters_is_kept_whole`, `test_a_quoted_value_of_61_characters_is_cut_after_60` |
| e | P8 | low | Process-mode child naming was neither documented nor tested | Documented in the GUIDE | `test_the_child_process_is_named_after_the_call` |
| e | A5 | low | The POSIX half of "misuse always surfaces" was untested | | `test_a_zero_budget_off_the_main_thread_still_reports_the_misuse` |
| e | OBS-P5 | | The grandchild fallback was caught only when the start method was set by hand | | `test_a_crash_behind_a_grandchild_is_seen_under_every_start_method` (fork, spawn and forkserver on POSIX) |

Kept as they are: an error raised by the caller's own `__reduce__` stays the cause of the
`PicklingError` with its text as written (lens c F2), while the message around it is
bounded. `Mode` is a cached `typing.Literal`, so an identical `Literal` written elsewhere
shows the same docstring.

Verification at 3309979 (fresh clones of the commit, fetched documents, pebble 5.2.3):

- Windows, CPython 3.13.2: `ruff format --check .`, `ruff check .`, `mypy --strict src`
  and `mypy --strict src tests` exit 0 (mypy also with `--platform linux` and `darwin`);
  `pytest` with `CALLTIMEOUT_E2E=1` exits 0 (202 collected). The changed test files also
  pass on CPython 3.11.5.
- WSL Ubuntu, CPython 3.14.4: the same static gates exit 0; `pytest` exits 0 under
  forkserver, fork and spawn (230 collected); the signal edge tests run 40 times in four
  parallel loops: 40 passed (the half-speed clock test failed 2 of 40 that way before).
- Lens e's survivors X1, X3, P8, W5, S7 and A5, run again with its own runner on the new
  tree: all killed under WSL forkserver, and X1, X3, P8 and W5 on Windows. Its P5 is now
  killed under the forkserver default by the new start-method test.

### Round 2, at e0eb7bc

The same five lenses. Lenses c and e confirmed every round 1 finding fixed. Every new
finding was fixed in 00f6889 and 6e2c03c; each behaviour fix has a contract that fails on
e0eb7bc (listed below) and passes now. Every behaviour change is in the CHANGELOG.

| Lens | Id | Severity | Finding | Fix | Contract |
| --- | --- | --- | --- | --- | --- |
| b, c, d, e | b N1, c N2, c N3, d N1, e W8 | medium | Under spawn and forkserver `prepickle` dropped one lock, queue or value per round and gave up after 100 (51 events), so valid calls were refused; each round pickled the whole call again, inside the budget (1M strings and 50 locks: `CallTimeout` after 11.5 s on a 5 s budget) | One trial pickle; if it fails, one rehearsal with a stand-in Popen set as the spawning Popen, so locks, queues and values pickle as they do in a start. No cap, and a call is pickled at most three times (trial, rehearsal, start) | `test_start_only_objects.py::test_any_number_of_start_only_objects_reach_the_child` (150 locks, 60 events, 120 values), `test_the_call_is_pickled_a_fixed_number_of_times_whatever_it_holds` |
| c | N1 | high | An object refused outside a start was dropped without checking its own state: a `Value` guarded by a `threading.Lock` (or of a local ctypes type) failed inside `Process.start()`, raw, and on Windows broke the next calls | The rehearsal pickles that state before any process exists | `test_sending_calls.py`, new case "start-only value guarded by a thread lock"; `test_a_lock_from_another_context_works_or_raises_the_documented_error` |
| b, c | b N2, c N4 | medium | A pipe end sent with a lock or queue left one duplicate handle per trial pickle open in the caller, so the reader never saw the end of the pipe and handles ran out | Trial and rehearsal pickle a stand-in for every pipe end and socket (after checking it is open); only the real pickling duplicates it, once, for the child | `test_a_pipe_end_sent_with_a_call_is_not_left_open_in_the_caller` (no extra, a lock, a lock and a queue; end of file on every call, and the open fd count on Linux) |
| c | N5 | low | The `PicklingError` message quoted 268 characters of the argument's repr, and the chained cause 100 KB | The message quotes pickle's error cut at 60 characters; the cause's text is cut at 300 in place; the GUIDE states both bounds | `test_a_quoted_secret_is_cut_in_the_message_and_in_the_chained_cause` |
| c | N6 | low | Signal mode armed the first tick for 1 us, so with a budget under 1 ms the only tick could be lost and the call ran to its end | No timer is armed for less than 1 ms, the first one included, and a budget under 1 ms counts as used up at once (the call is not started, as with zero); `run` docstring, GUIDE, CHANGELOG | `test_signal_floor.py::test_a_budget_under_a_millisecond_counts_as_used_up_and_never_starts_the_call`, `test_no_arm_is_shorter_than_the_floor_toward_an_enclosing_timer_due_sooner` |
| a, d | a N1, d note | low | `Mode.__doc__ = ...` relabelled typing's cached `Literal["thread", "process", "signal"]`, also the caller's own identical alias | No assignment: `Mode` is documented, with its example, in a section of the package docstring | `test_contract.py::test_importing_the_package_leaves_typings_cached_literal_alone`, `test_mode_is_documented_in_the_package_docstring_with_an_example_that_runs` |
| a, e | a N2, e W10, e W12 | low | The CHANGELOG said the notes were "ten at most", but a summary note follows them; nothing pinned the cap or the summary | Reworded in the CHANGELOG and GUIDE: the first ten are kept, each cut after 60 characters, followed by a count of the rest | `test_the_notes_pickle_adds_are_the_first_ten_and_a_count_of_the_rest` (CPython 3.14) |
| e | N11 | medium | The cycle guard of `_caused_by` was untested; without it a cyclic `__cause__` chain after the timeout hung signal mode | | `test_an_error_with_a_cause_cycle_after_the_timeout_still_returns` |
| e | W5 | medium | A reduce raising `RuntimeError` from a frame with a local `obj` passed for `assert_spawning` once its frame check was dropped | The frame check is gone (the rehearsal replaces the search); the argument shape stays pinned | `test_sending_calls.py`, new case "reduce raising RuntimeError like assert_spawning" |
| e | W15 | low | Nothing checked that the message names the inner error | | `test_the_message_names_what_could_not_be_pickled` |
| e | D4 | low | A module whose lazy `__getattr__` raises `ImportError` was not covered by the decorator's lookup tests | | `test_decorator.py::test_process_mode_sends_a_callable_from_a_module_whose_getattr_raises` |
| e | D6 | low | Function attributes copied by `_keep_metadata` were not checked | | `test_attributes_set_on_the_wrapped_function_are_kept` |
| e | N2, N3 | low | The floor was only tested on re-arms toward the deadline, not toward an enclosing timer due sooner | The floor now lives in `arm()` itself, for every arm | `test_no_arm_is_shorter_than_the_floor_toward_an_enclosing_timer_due_sooner` (an enclosing handler re-arming itself 200 us ahead), `test_an_early_tick_never_re_arms_for_less_than_the_floor` |
| e | N4 | low | A tick inside the last millisecond was only required to end the call, not to end it there | | `test_a_tick_inside_the_last_millisecond_ends_the_call_without_re_arming` |

Round 1's remark that an identical `Literal` shows calltimeout's docstring no longer
applies.

Verification:

- Contracts first: the new and changed test files run against e0eb7bc's `src` fail with
  13 failures under WSL CPython 3.14.4, forkserver and spawn (the many-objects, pickle
  count, pipe, secret, other-context lock, guarded `Value`, sub-millisecond budget,
  enclosing-timer floor and both `Mode` contracts), and the process ones also on Windows
  CPython 3.13.2. The other new tests pin behaviour that was already right and kill the
  lens e survivors.
- WSL Ubuntu, CPython 3.14.4, fresh clone of 6e2c03c: `ruff format --check .`,
  `ruff check .`, `mypy --strict src` and `mypy --strict src tests` exit 0; `pytest`
  exits 0 under forkserver, fork and spawn; the two signal timing files run 40 times in
  four parallel loops: 40 passed.
- Windows, CPython 3.14.2, fresh clone of 6e2c03c from GitHub on another machine, with
  the fetched documents, pebble 5.2.3 and `CALLTIMEOUT_E2E=1`: the same static gates
  and `pytest` exit 0.
- Twelve mutants of the new code (cycle guard, arm floor, last-millisecond window,
  sub-millisecond budget, notes cap, notes summary, message detail, pipe stand-in, no
  stand-in Popen, uncut cause, message limit, no rehearsal), WSL forkserver: all killed.
  Lens e's D4 and D6 are killed on Windows.
- The lenses' own probes on Windows CPython 3.13.2: 101 and 256 locks pass; 1M strings
  with 50 locks finish in 0.67 s on a 5 s budget; a `Value` guarded by a thread lock and
  a `Value` of a local ctypes type raise `PicklingError` and 0 of 10 later calls fail;
  a pipe end with 0, 1 or 3 locks reaches end of file on all 20 calls (handles 125 to
  128); the secret message is 109 characters and its cause 303.

### Round 3, at c703b47

The same five lenses. Every round 2 finding was confirmed fixed by the lens that raised
it. Every new finding is fixed; each behaviour fix has a contract that fails on c703b47
and passes now, and every behaviour change is in the CHANGELOG.

| Lens | Id | Severity | Finding | Fix | Contract |
| --- | --- | --- | --- | --- | --- |
| a, b, c, d, e | a A1, b N3, c N7, d N2, e E3-1 | medium | A pipe end or socket in a call stayed open in the caller when the budget ran out while pickling the call (every platform, no process started) or before the child loaded it (POSIX spawn and forkserver through `resource_sharer`, with tracebacks on the caller's stderr under forkserver; Windows through the duplicate made for the child to take), so the GUIDE's "never left open in the caller" was false | Pipe ends, sockets and proxies are never pickled outside `Process.start()`: the trial pickle replaces each by its index and the start pickles them (`_parcel.Parcel.__reduce__`). On Windows a pickler of the start duplicates a pipe end straight into the child (`Popen.duplicate_for_child`) and shares a socket with the child's pid, so nothing waits in the caller; on POSIX the start passes the descriptors itself. GUIDE and CHANGELOG reworded to what holds | `test_handles.py::test_an_end_in_a_call_whose_pickling_used_up_the_budget_is_not_left_open` (pipe end, socket, socket `Connection`; no process started), `test_an_end_in_a_call_stopped_before_its_child_loads_it_is_not_left_open` (each kind, with and without a lock) |
| a, d | a A3, d N2 (c) | low | Windows: every process-mode call stopped before its child loaded leaked one handle (the result pipe's write end), whatever it held | The write end goes through the same hand-over | `test_calls_stopped_before_their_child_loads_leave_no_handle_behind` (handle count over 15 calls) |
| d | N3 | low | A proxy of a manager with its own authkey failed in the child with `AuthenticationError` (pickled outside a start, it lost the authkey) unless the call also held a lock | Proxies are held back like pipe ends and pickled by the start | `test_sending_calls.py::test_a_proxy_of_a_manager_with_its_own_authkey_reaches_the_child` |
| a, c | a A2, c N8 | low | The chained pickle error was cut only when it carried one argument; one whose text comes from `__str__` was chained whole (100,007 characters), and one whose `args` cannot be set made `run` raise a raw `AttributeError` | `_bounded` never raises: it cuts the error in place when its `args` carry its text and checks the result; otherwise a `RuntimeError` naming its type, cut after 300 characters, stands in as the cause; GUIDE and CHANGELOG say so | `test_bounded_causes.py::test_the_chained_error_is_cut_after_300_characters_whatever_raised_it` (read-only `args`, text from `__str__`, two args, one long arg) |
| c | N9 | low | An argument whose `__class__` property raises was refused, though `multiprocessing` sends it | The trial tests `type(obj)`, as pickle dispatches | `test_an_argument_whose_class_attribute_raises_is_sent_as_it_pickles` |
| e | E3-2 (H1) | medium | Dropping `socket.socket` from the handle types survived: only pipes were tested | | `test_a_socket_sent_with_a_call_is_not_left_open_in_the_caller` (with and without a lock), plus the socket cases above |
| e | E3-3 (H2) | low | Dropping `Connection` survived on Windows: a Listener/Client connection was untested | | `test_a_socket_connection_sent_with_a_call_is_not_left_open_in_the_caller`, plus the socket `Connection` cases above |
| e | E3-4 (H6) | medium | Removing the closed-socket check survived; with a lock the raw `OSError` escaped from the start and broke the next call on Windows | | `test_a_closed_end_raises_pickling_error_and_spoils_no_later_call` (closed socket and closed pipe end, with and without a lock, no process started, next call works) |
| e | E3-5 (P3, P4) | low | A failure of the second pickling of a call holding a pipe end was not pinned | That second pickling is gone: the objects beside a pipe end are pickled once, before the start. The same shape remained on the lock path (rehearsal, then the start): a lock and an object that pickles only once raised a raw `TypeError` from `Process.start()`, and on Windows the next call failed with `CallCrashed` (reproduced on CPython 3.13.2). Now a failure of the start's pickling is caught inside it, the start completes, the child exits without running anything, and the caller stops it and raises the documented, bounded `PicklingError`; GUIDE and CHANGELOG | `test_the_objects_beside_an_end_are_pickled_once_before_the_start`, `test_start_only_objects.py::test_a_call_that_pickles_for_the_rehearsal_but_not_for_the_start_raises_pickling_error` (both orders, three later calls), `test_the_error_of_a_start_that_cannot_pickle_the_call_is_bounded` |
| e | E3-6 (B2, U3) | low | The 300-character cut was only asserted as a maximum | | `test_exactly_300_characters_of_the_chained_error_are_kept`, `test_exactly_300_characters_of_a_results_pickling_error_are_kept` |
| e | E3-7 (B3) | low | A pickle error whose `__str__` raises was untested | | `test_an_error_whose_str_raises_still_gives_pickling_error` |
| e | E3-8 (F5) | low | The 1 ms boundary of signal mode was untested | | `test_signal_floor.py::test_a_budget_of_exactly_a_millisecond_starts_the_call` |

Also changed: the load error of a child that cannot import the call now points at
`Parcel.open()` (`test_a_call_the_child_cannot_load_reports_the_real_error` updated), and
the pebble oracle asks pebble again in a fresh pool when pebble's own pool breaks under
load ("Unexpected error within the Pool", seen with no calltimeout call running), since
that answer is no verdict on the call.

Verification:

- Contracts first: the round 3 contract files of db26ef1 run against c703b47's `src` fail
  with 20 failures on Windows CPython 3.13.2 (every pipe end, socket and socket
  `Connection` case, the handle count, the closed pipe end, the pickled-once case, three
  bounded-cause cases, the proxy, the `__class__` argument and both start-pickling cases)
  and 16 under WSL CPython 3.14.4, spawn and forkserver (the same less the Windows-only
  ones: with a lock, a call stopped early already left no end open on POSIX). The other
  new tests pin behaviour that was already right and kill lens e's survivors.
- WSL Ubuntu, CPython 3.14.4, fresh clone of db26ef1 from GitHub: `ruff format --check .`,
  `ruff check .`, `mypy --strict src` and `mypy --strict src tests` exit 0; `pytest`
  exits 0 under forkserver, fork and spawn.
- Windows, every interpreter on this PC, fresh clone of db26ef1 from GitHub: the wheel
  and sdist built once, the wheel installed in a fresh venv per interpreter and the
  sdist's own suite run with `src` removed, `CALLTIMEOUT_E2E=1`, the fetched documents
  and pebble 5.2.3, plus the installed package's doctests: CPython 3.10.19, 3.11.5,
  3.12.12 and 3.13.2 each 235 passed, 16 skipped; 3.14.2 and 3.14.2 free-threaded each
  236 passed, 15 skipped; doctests 5 passed on each. The static gates exit 0 on this PC
  (mypy also for the Linux and macOS platforms) and `pytest` in the repository exits 0.
- Twenty-five mutants of the new code, each in a fresh tree with the contract files run:
  under WSL forkserver 21 run, 20 killed (M1, M2, M4 to M8, M13 to M25) and M9 (the result pipe's
  write end pickled by the start's plain pickler) equivalent there, since on POSIX that
  pickler is the start's own; on Windows M1 to M4, M6 to M12, M14, M21 and M23 to M25 all
  killed. M3 and M10 to M12 only change Windows code.
- The lenses' own repros on Windows CPython 3.13.2: lens e's SOCK, CONN, CLOSED, ONCE,
  BADSTR, CAUSE, RESULT, LEAK and LEAK2 probes give the expected answers (end of pipe
  or socket seen every time, closed socket refused and the next call 2, cause 303
  characters, result message 342); lens a's handle probe grows by 0 over 30 calls at
  budgets 60 s, 0.3 s and 0.02 s (it grew 30 at 0.02 s before).

### Round 4, at bef8e0c

The same five lenses. Every round 3 finding was confirmed fixed by the lens that raised
it (a A1 to A3, b N1 to N3, c N7 to N9 and the round 2 re-checks, d N1 to N3, e all
eight). Every new finding is fixed; each behaviour fix has a contract that fails on
bef8e0c and passes now, and every behaviour change is in the CHANGELOG.

| Lens | Id | Severity | Finding | Fix | Contract |
| --- | --- | --- | --- | --- | --- |
| b, d | b N4, d N4 | medium | Every process-mode call that ended in an error (its function raised, or the start could not pickle it) kept the child's process object and its 2 descriptors (POSIX) or handles (Windows) alive in a reference cycle until a garbage collection, so a loop of failing calls hit `EMFILE` (call 122 to 242 at `ulimit -n 256`, call 506 at 1024) | `_process._stop` closes the process right after joining it, and the raised error is no longer held in a local of the raising frame (`_wire.unpack`, the refused branch, `_rehearse`) | `test_error_paths.py::test_calls_that_raise_leave_no_handle_open` (30 calls, collector off), `test_calls_the_start_could_not_pickle_leave_no_handle_open` (20 calls) |
| c | N12 | low | A `BaseException` (a `KeyboardInterrupt`) raised while the start pickled a held object escaped `Parcel.__reduce__`, so `Process.start()` failed half way; on Windows later calls passing pipe ends then lost what the child sent | `Parcel.__reduce__` records any `BaseException`; the start finishes, the caller stops the child, then raises the documented `PicklingError` for an `Exception` and anything else as it came | `test_a_base_exception_raised_while_the_start_pickles_is_raised_as_it_is` (`KeyboardInterrupt` and `SystemExit`, from a held proxy and from an object beside a lock: the same object raised, nothing escapes the start, no spawning start left, five later pipe-end calls deliver) |
| c | N13 | low | Under forkserver a call with 250 or more pipe ends or sockets failed with an undocumented `OSError` (`ValueError` from 252) from the start, while the GUIDE promised any number | The descriptors a forkserver start will pass are counted before any process exists (pipe ends and sockets held back by the trial, plus what the rehearsal duplicates for queues and shared memory); more than 248 (Linux carries 253 in one message, the fork server adds 4 and the start the result pipe) raises `pickle.PicklingError`. GUIDE and CHANGELOG state the limit | `test_descriptor_limit.py`: 248 pipe ends reach the child and 249 (also with a lock) are refused with no process started; 124 queues pass and 125 are refused; 300 pipe ends reach the child under spawn and fork |
| a, b, c | a A4, b INFO, c O2 | low | The bounded cause kept its own `__context__` and `__cause__`, so an argument whose `__reduce__` raised while handling, or from, an error quoting the argument printed it whole (7,500 to 102,000 characters) | The new `_causes.bounded` drops the errors chained to the cause | `test_hostile_causes.py::test_the_printed_error_of_a_call_that_cannot_be_sent_stays_short` (raised from a huge error, while handling a huge error and a huge interrupt; before the start and in it) |
| c | N10 | low | A pickle error whose type refuses `__qualname__` made `_bounded` raise, so `run` raised a raw `RuntimeError` with the 100,007-character original as its context | The stand-in's type name is computed inside a guard, falling back to a fixed text | the same test, "type that cannot be named" |
| c, b | c N11, b INFO | low | The text bound could be defeated: a `__str__` returning a `str` subclass that lies about its length, a `__str__` that changes between reads, and `__notes__` set to a `str` or a tuple were printed whole | The text is read once as a plain `str`. Only the plain errors pickle raises (`TypeError`, `ValueError`, `RuntimeError`, `pickle.PicklingError` and a few more, exact types) are cut in place, their `args` replaced by that one cut text; any other is replaced by the `RuntimeError` stand-in naming its type. Notes are read from the instance dict and bounded whatever their container (a `str` or a tuple included); the `repr` quoted in messages is read as a plain `str` too | the same test: a lying `str`, a `__str__` that flips, an argument whose `__str__` flips, notes as a `str` and as a tuple |
| b | N5 | low | The GUIDE's errors table said the `PicklingError` for an unsendable call is raised before any process starts, which the start-time refusal contradicts (the README said the same) | Reworded: raised before the call runs (before any process starts, or once the child is stopped for a call that fails only when the start pickles it) | docs |
| e | E4-1 (S1) | medium | Rebuilding every held object as the first one survived: no test sent two held objects in one call | | `test_sending_calls.py::test_each_end_socket_and_proxy_in_one_call_reaches_its_own_peer` (two pipe ends, a socket and a manager proxy) |
| e | E4-6 (S31) | medium | Catching only `TypeError` at the start survived | | `test_a_call_that_pickles_for_the_rehearsal_but_not_for_the_start_raises_pickling_error` parametrized over `TypeError`, `ValueError`, `RuntimeError`, `PicklingError` and `RecursionError`, asserting the cause keeps its type; `test_an_error_raised_while_the_start_pickles_a_held_proxy_is_the_documented_one` |
| e | E4-2 (S20), E4-3 (S26) | low | The in-place cut was only checked on huge errors and by length | | `test_bounded_causes.py::test_a_plain_error_is_cut_in_place_after_exactly_300_characters` (300, 301, 400, 599 and 5,000 characters, one and two args: exact text, type kept) |
| e | E4-4 (S22, S23) | low | The stand-in's type and its quoted type name were unchecked | | `test_an_error_that_cannot_be_cut_in_place_is_replaced_by_a_runtime_error_naming_it` |
| e | E4-5 (S24) | low | The stand-in's notes were unchecked | | `test_hostile_causes.py::test_the_stand_in_keeps_the_notes_pickle_added_bounded` (Python 3.11 and later, skipped where pickle adds no notes) |
| e | E4-7 (S7) | low | Restoring the spawning start after a rehearsal was unchecked on POSIX | | `test_error_paths.py::test_a_call_that_fails_its_rehearsal_leaves_no_spawning_start_behind` |

Also changed: a closed pipe end or socket in a call is refused with a `ValueError` (it was
an `OSError`, which has a `__str__` of its own and would now be replaced by the
stand-in); the test of an error whose `__str__` raises now expects the stand-in naming
`BadStr`. The tests' handle counter moved to `tests/_counting.py`, and the author mutant
M41 points at the constant in its new module.

Observations the lenses reported outside their findings, left as they are: a pipe end
returned as a call's result arrives wrapping the child's descriptor number (lens a, also
at c703b47), and the coroutine check reads a result's `__class__` (lens c O3, in code
unchanged since 0.2.0).

Verification:

- Contracts first: the round 4 contract files run against bef8e0c's `src` fail on Windows
  CPython 3.13.2 (both handle counts, all four interrupt cases, every hostile shape except
  the type that cannot be named, which crashes pytest's own reporting there, and the test
  of an error whose `__str__` raises) and under WSL CPython 3.14.4 (forkserver: the same
  plus both descriptor-limit tests; spawn: the same without them; fork: the handle count
  of calls that raise). The other new tests pin behaviour that was already right and kill
  lens e's survivors.
- Windows, Elena's PC, CPython 3.14, committed head: `ruff format --check .`,
  `ruff check .` and `mypy --strict src tests` exit 0; `pytest` with `CALLTIMEOUT_E2E=1`,
  the fetched documents and pebble 5.2.3: 292 passed, 20 skipped and one failure (the
  wheel contract did not list the new module), fixed in 388e62b and that file run again:
  5 passed.
- Windows, this PC, fresh clone of 388e62b: `pytest` on CPython 3.10.19, 3.11.5, 3.12.12
  and 3.13.2 each 286 passed, 27 skipped; 3.14.2 free-threaded 288 passed, 25 skipped
  (POSIX-only and opt-in e2e tests). `mypy --strict src tests` exits 0 for the Windows,
  Linux and macOS platforms.
- WSL Ubuntu, CPython 3.14.4, 388e62b: format, lint and `mypy --strict src tests` exit 0;
  `pytest` under forkserver 332 passed, 9 skipped; spawn 331 passed, 10 skipped; fork 246
  passed, 95 skipped.
- The lenses' repros: at `ulimit -n 256`, 300 calls that raise leave 4 to 6 descriptors
  open under spawn, forkserver and fork and the next call returns, and 200 refused calls
  leave 5 or 6 (spawn, forkserver); lens c's interrupting proxy, 4 rounds of 10 pipe-end
  calls on Windows CPython 3.13.2 and 3.14.2 free-threaded: 0 undelivered (4 at bef8e0c,
  with `UnpicklingError` tracebacks from the half-started children); under forkserver
  247 pipe ends, 120 `Value` and 5 `Array` objects pass (their shared memory is one
  descriptor) and 248 pipe ends plus a `Value` are refused.

### Round 5, at 8d57e0c: lens e survivors

Lens e's own mutation round over the round 4 code left 18 mutants alive. No library code
changed: each one got a contract in 9f00374 or 5b84b46, or is shown equivalent where it
lives.

| Id | Mutation | Contract |
| --- | --- | --- |
| N7 | the forkserver count leaves out what the rehearsal duplicates | `test_descriptor_limit.py` (queues and shared memory counted) |
| N9 | each duplicate counted twice | `test_descriptor_limit.py` |
| N10 | every held object counted as a descriptor | `test_descriptor_limit.py` (proxies beside pipe ends) |
| N11 | a closed end refused with `OSError` | `test_handles.py::test_a_closed_end_raises_pickling_error_and_spoils_no_later_call` (exact cause type) |
| N12 | a `str` subclass argument taken as plain | `test_hostile_causes.py`, "str arg whose str changes between reads" |
| N13 | an error with two args left as it is | `test_hostile_causes.py`, "second arg whose repr changes between reads" |
| N14 | an error whose text cannot be read replaced by the stand-in, not cut in place | `test_cause_details.py::test_a_plain_error_whose_argument_has_no_str_is_cut_in_place` |
| N21 | the stand-in loses the frames of the failure | `test_cause_details.py::test_the_stand_in_keeps_the_frames_where_the_argument_failed` |
| N23 | the count of dropped notes off by ten | `test_cause_details.py::test_ten_notes_are_kept_and_the_rest_counted` |
| N24 | notes set to a `str` dropped | `test_cause_details.py::test_notes_set_to_a_str_are_kept_as_one_cut_note` on CPython 3.10 to 3.13; equivalent on 3.14, where pickle cannot add its note to such an error and raises a new one in its place, so a `str` never reaches the cut |
| N25 | a note read without `str.__str__` | `test_hostile_causes.py`, "a note that lies about its length" |
| N26 | notes that cannot be kept left on the error | `test_hostile_causes.py`, "notes set to a list subclass" |
| N27 | notes written even when none are kept | `test_cause_details.py::test_a_cause_without_notes_gets_none_and_takes_new_ones`, now also with notes held in a list subclass, which pickle 3.14 keeps on the error (left as `None`, `add_note()` would fail) |
| N28 | a `str` subclass text kept as given | `test_hostile_causes.py`, "arg whose str lies about its length" |
| N29 | the message quotes `str` of pickle's error, not its `repr` | `test_cause_details.py::test_the_message_quotes_the_repr_of_pickles_error` |
| N32 | the child's process object not closed after the join | `test_handle_release.py::test_the_errors_of_calls_that_raised_hold_no_handle_of_their_child` |
| N35 | the raised error kept in a local of `unpack` | `test_handle_release.py::test_an_end_sent_with_a_call_that_raised_is_closed_once_the_caller_drops_it` |
| N36 | the error of a failed rehearsal kept in its frame | `test_handle_release.py::test_an_end_sent_with_a_call_that_failed_its_rehearsal_is_closed_once_dropped` |

Verification:

- Windows, another machine, CPython 3.14, fresh clone of 9f00374: format, lint and
  `mypy --strict src tests` exit 0; `pytest` with `CALLTIMEOUT_E2E=1`, the fetched
  documents and pebble 5.2.3 exits 0. The Windows mutants there: all killed but N24 and
  N27 (the forkserver ones do not apply).
- At 5b84b46: N24 and N27 killed on CPython 3.13.2 (this PC); on 3.14.2 N27 killed and N24
  survives, equivalent as above.
- WSL Ubuntu, CPython 3.14.4, fresh clone of 5b84b46: `ruff format --check .`,
  `ruff check .`, `mypy --strict src` and `mypy --strict src tests` exit 0; `pytest`
  exits 0 under forkserver, fork and spawn. The 18 mutants under forkserver: all killed
  but N24; under spawn N7, N9 and N10 also live, since the descriptor count only runs for
  a forkserver start.
- Windows, every interpreter on this PC, fresh clone of 5b84b46 from GitHub: the wheel
  and sdist built once, the wheel installed in a fresh venv per interpreter and the
  sdist's own suite run with `src` removed, `CALLTIMEOUT_E2E=1`, the fetched documents
  and pebble 5.2.3, plus the installed package's doctests: CPython 3.10.19, 3.11.5,
  3.12.12 and 3.13.2 each 310 passed, 21 skipped; 3.14.2 and 3.14.2 free-threaded each
  311 passed, 20 skipped (POSIX-only and forkserver-only tests); doctests 5 passed on each.

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

## Disputed findings

None in rounds 1 to 6.
