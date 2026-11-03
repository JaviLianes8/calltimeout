# QA findings and verification

### Round 7, at f942bc9

The five lenses again, each with fresh agents. Lens a ran the 28 doctests, every README
and GUIDE example (Windows 3.10 to 3.14, Linux fork, spawn and forkserver), `mypy --strict`
on the documented blocks and a probe of 71 to 79 documented claims; lens b re-derived
results against pebble 5.2.3, plain `multiprocessing`, the CPython `multiprocessing` and
`_sre` sources and the kernel's descriptor limit, on Windows 3.10 to 3.14 and Linux 3.12 to
3.14; lens c fuzzed 1,250 seeds on Windows and Linux with hostile names, sizes and types;
no finding came from lens d; lens e ran mutants of its own, three of which survived. Every
finding is fixed in 88d5474 (two of its contracts made importable and exact in 6dc407f and
0fef2be), and 05d15a6 reflows one GUIDE paragraph. Each behaviour fix has a contract that
fails on f942bc9 and passes now, and every behaviour change is in the CHANGELOG.

| Lens | Id | Severity | Finding | Fix | Contract |
| --- | --- | --- | --- | --- | --- |
| b | B1 | medium | Signal mode let an enclosing interval timer drift: each tick due during a call was counted from when it ran, so up to 1 ms per tick added up and ticks were lost (400 calls of 5 ms under a 10 ms timer: about 10 ticks lost, the last 120 to 130 ms late); a timer read between a tick and its delivery (Linux shows no delay left) was left disarmed | `_signal._next_tick` counts the next tick from when the last was due, skipping whole intervals missed; `_outer_timer` treats a read of no delay but an interval as a timer still running | `test_signal_intervals.py`: a 10 ms timer across one 1.5 s call and across 200 calls of 5 ms loses no tick and ends less than 4 ms behind schedule, like the same timer around plain sleeps; a timer read as it fires is kept with its interval |
| c | F1 | medium | `_text.cut` trusted `str` subclasses, so a name or text lying about its length went whole (a million characters) into every argument error, the coroutine error, thread and child names, `CallTimeout` and `CallCrashed`, and the child's `RuntimeError` stand-in | `cut` measures `str.__str__(text)`; names are read only when they are text | `test_hostile_names.py`: every argument check, a lying function name (error, thread and process names), lying numbers in both exceptions, an unpicklable child error with a lying text |
| a | A1 | low | The process-mode cause shown in the GUIDE was the private `calltimeout._wire.RemoteTraceback`, in every traceback and in its pickle | `RemoteTraceback` exported, shown and pickled as `calltimeout.RemoteTraceback`, with a docstring and doctest; README and GUIDE describe it | `test_contract.py`, `test_contract_api.py::test_remote_traceback_is_an_exception_whose_text_is_the_childs_traceback` and `test_public_objects_live_under_the_package_name`, `test_process.py::test_an_exception_comes_back_with_the_childs_traceback` (no `_wire` in the printed chain or the pickle) |
| a | A2 | low | `with_timeout(mode="process")` under `@classmethod` raised `PicklingError` under spawn and forkserver: the name leads to a bound method | `_decorator._through_class` sends such a wrapper through its class (`_ClassMethodCall`), found again in the child as `getattr(cls, name).__func__`; GUIDE and docstring list the method kinds that work | `test_decorator.py::test_process_mode_runs_methods_of_every_kind_in_their_own_child` (instance method, staticmethod and classmethod, on a class and a subclass, each in its own child) |
| c | F2 | low | `type_name` and `call_name` read `__name__` and `__qualname__` unguarded: a metaclass whose name raises (or is not text) let that error escape from `run`, also for a callable that runs fine when called | Both read through `_text._name`, falling back to `<unnamed type>` or `<unnamed callable>` | `test_hostile_names.py::test_every_argument_check_names_a_hostile_type_briefly` (raising and non-text names, every argument), `test_a_callable_whose_type_refuses_its_name_still_runs` (thread and process mode) |
| c | F3 | low | A child error whose type's `__module__` raises crashed the child (`CallCrashed(1)`), because formatting its traceback raised | `_wire._formatted` falls back to a bounded placeholder, and the stand-in's name comes from `full_type_name` | `test_hostile_names.py::test_a_child_error_whose_type_refuses_its_module_still_arrives` (thread and process mode) |
| c | F4 | low | `-10**400` and `Fraction(-10**400, 3)` were reported as above `TIMEOUT_MAX` | The `OverflowError` branch checks the sign | `test_validation.py::test_a_negative_timeout_too_large_for_a_float_is_called_negative`; the positive case stays above the limit |
| b | B3 | low | The forkserver descriptor message left out the shared-memory block of `Value` and `Array` objects, which it counts | The message lists "one per shared-memory block" | `test_descriptor_limit.py::test_the_limit_message_names_every_kind_of_descriptor_it_counts` and the shared-value test |
| a | A3 | low | The GUIDE's `RuntimeError` row left out an unpicklable exception from a process-mode call | Row extended | docs |
| b | B2 | low | The GUIDE gave a regular expression match as C code that cannot be interrupted; `_sre` checks for signals every 4096 steps | Examples now `sorted()` of a huge list and `sum()` over a long `range`, and "some C code checks for signals" (GUIDE and the `run_with_signal` docstring) | docs |
| c | F5 | low | Rebuilding the result in the caller is outside the budget and not interrupted, undocumented | GUIDE next to the pickling caveat, `run` and `run_in_process` docstrings | docs |
| e | F1-V15 | low | `if not kwargs:` for `if kwargs is None:` survived | | `test_validation.py::test_rejects_kwargs_that_are_falsy_but_not_a_mapping` (`[]`, `0`, `""`, `()`, `b""`, every mode, nothing started) |
| e | F2-D07 | low | `with_timeout` skipping the check of a non-callable when applied survived | | `test_decorator.py::test_applying_the_decorator_to_something_not_callable_raises_at_once` |
| e | F3-A07/A08 | low | `CallTimeout` keeping the private `Expired` as its context survived | | `test_errors.py::test_a_timeout_never_shows_the_private_signal_behind_it` (every mode, budgets 0.05 and 0: context suppressed, neither "Expired" nor "During handling" in the printed traceback) |

Lens b's entry B0 records the claims that held and is not a defect. Observations outside
the findings, left as they are: the README link to `blob/main/GUIDE.md` answers 404 until
`release/1.0.0` is merged; `CallCrashed.exitcode` is typed `int | None` and is an `int` in
practice; `shown()` builds the whole `repr` of a bad mode before cutting it; a finished
child with a non-daemon thread that ignores SIGTERM delays the return by up to the
documented 1 s grace period.

Mutants, each applied alone, killed by the contract named above: V15, D07, A07, A08, and
nine on this round's fixes (R1 the next tick counted from now, R2 a timer read as it fires
taken as disarmed, R3 `cut` without the exact `str`, R4 the unguarded type name, R5 no
classmethod route, R6 unguarded traceback formatting, R7 no sign check, R8 the old
descriptor message, R9 `RemoteTraceback` left under `_wire`). All 13 killed on WSL under
forkserver; the 11 that run on Windows (all but the two signal ones) killed under spawn.

Verification:

- WSL Ubuntu, CPython 3.14.4, fresh clone of 05d15a6: `ruff format --check .`,
  `ruff check .`, `mypy --strict src` and `mypy --strict src tests` exit 0; `pytest`
  under forkserver 428 passed, 11 skipped; fork 319 passed, 120 skipped; spawn 425
  passed, 14 skipped.
- The new contracts on the src of f942bc9: 29 fail under forkserver, 27 under fork (the
  classmethod contract passes under fork, which pickles nothing) and 25 on Windows spawn
  (the POSIX signal contracts skip there). The contracts for lens e's survivors pass
  there, as they pin behaviour f942bc9 already had.
- Windows, this PC, fresh clone of 05d15a6 from GitHub: the wheel and sdist built twice
  (byte-identical, wheel sha256 0a7f729b...e757) and installed per interpreter, the sdist's
  own suite run with `src` removed, `CALLTIMEOUT_E2E=1`, the fetched documents and pebble
  5.2.3, plus the installed package's doctests (6 passed on each): CPython 3.10.19 366
  passed, 24 skipped; 3.11.5, 3.12.12 and 3.13.2 367 passed, 23 skipped; 3.14.2 and
  3.14.2 free-threaded 368 passed, 22 skipped.
- The gates on this PC at 05d15a6 (CPython 3.13.2, ruff 0.17.0, mypy 2.4.0, `mypy
  --strict src tests` for the Windows and Linux platforms): all exit 0.

