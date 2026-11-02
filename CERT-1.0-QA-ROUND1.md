# QA findings and verification

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

