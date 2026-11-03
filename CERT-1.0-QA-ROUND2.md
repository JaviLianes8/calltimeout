# QA findings and verification

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

