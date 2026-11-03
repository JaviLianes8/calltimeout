# QA findings and verification

### Round 8, at ebcc8c1

Lenses a, b, c and e, each with fresh agents. Lens a ran the doctests (Windows 3.11 and
3.13, Linux 3.14 under each start method), every README and GUIDE block as a script, the
GUIDE errors table, `mypy --strict` as a consumer, and checked the README's "Why" facts and
the CHANGELOG against PyPI and git; lens b re-derived signal and process behaviour against
the Linux 6.6 sources, raw `multiprocessing`, `ThreadPoolExecutor` and pebble 5.2.3; lens
c fuzzed arguments (seeds 11 to 14) and process payloads (seeds 21 and 22) and probed
stalled and stopped children; lens e ran 56 mutants of its own on Windows, 9 of which
survived. Every finding is fixed in 052f156 (signal mode), 43cc306 (the rest), e2db93d
and be35644 (two contracts tightened). Each behaviour fix has a contract that fails on
ebcc8c1 and passes now, and every behaviour change is in the CHANGELOG.

| Lens | Id | Severity | Finding | Fix | Contract |
| --- | --- | --- | --- | --- | --- |
| b | F1 | high | Signal mode: a `SIGALRM` taken right after the call put its handler in place ran it before `previous` was bound (`NameError`), outside the `try` that restores the handler, so the handler stayed installed for good | `previous` is read before the handler goes in; a tick taken before the call's timer is set is held and handled once it is; the whole set-up is inside the `try` that restores the handler | `test_signal_races.py::test_a_tick_on_its_way_as_the_call_starts_reaches_the_enclosing_handler`, `test_many_quick_calls_under_a_fast_enclosing_timer_keep_its_handler` (1 ms interval timer, 0.5 s of calls) |
| b | F2 | high | Signal mode: an enclosing tick due as a call started was taken by the call as its own and dropped, so an outer signal-mode deadline could be lost and the call run forever | The enclosing timer is read and replaced in one `setitimer`; a tick that is not the call's own (its timer still running) goes to the previous handler, never dropped | `test_signal_races.py::test_an_outer_deadline_due_as_an_inner_call_starts_is_not_lost` |
| b | F3 | medium | Signal mode: an enclosing timer drifted over many calls (one-shot up to 18 ms early, interval timers late, ticks lost and doubled) | `_timers.kept` keeps the exact schedule the previous call gave back when the timer read matches it within 0.5 ms; `_timers.settle` lets a tick due within 0.2 ms through before the timer is taken. Measured on WSL (Linux 6.6): a timer replaced in the instant it expires loses its tick (130 of 300 trials), which is where most lost ticks came from | `test_signal_races.py::test_an_interval_timer_keeps_every_tick_on_schedule_over_many_calls` (calls that time out, calls that end in time, quick calls: none lost or doubled, under 4 ms late) and `test_a_one_shot_timer_fires_on_time_across_many_quick_calls` |
| c | C1 | medium | Process mode: a child error whose pickle rebuilds as something other than an exception crashed the caller with `AttributeError` or `TypeError` from `_wire.unpack` | `pack_error` sends the `RuntimeError` stand-in for such an error; `unpack` checks the payload too | `test_child_outcomes.py::test_a_child_error_that_rebuilds_as_something_else_arrives_as_a_stand_in` (rebuilt as a `str` and as an object) |
| c | C2 | medium | Process mode: a call that pickles in the caller but cannot be loaded in the child raised pickle's raw error, unbounded (a million-character message), with no row in the errors table | `_child._outcome` raises the documented `pickle.UnpicklingError` ("the call cannot be loaded in the child process"), its cause bounded like the send side; GUIDE bullet and errors row | `test_child_outcomes.py::test_a_function_the_child_cannot_find_raises_a_bounded_unpickling_error` (a million-character name), `test_an_argument_that_fails_to_rebuild_in_the_child_raises_a_bounded_unpickling_error`; `test_hardening.py::test_a_call_the_child_cannot_load_reports_the_real_error` updated |
| c | C3 | medium | POSIX process mode: once the result started arriving, `recv_bytes()` had no deadline, so a child stalled between the header and the body blocked `run` for good | `_process._receive` reads under a watchdog thread that terminates the child at the deadline and kills it after the grace period; a read cut short that way is a timeout. The GUIDE says the budget covers receiving the result | `test_child_outcomes.py::test_a_child_that_stalls_while_sending_its_result_still_ends_at_the_deadline` (asleep: ends within 0.3 s of the deadline; stopped with `SIGSTOP`: killed after the grace period) |
| a | A1 | medium | Generator and async generator functions passed the async check, and their body ran with no budget once iterated | `check_call` refuses coroutine, async generator and generator functions; a call returning an async generator is refused like a coroutine; GUIDE and errors row | `test_validation.py::test_rejects_a_function_whose_body_the_call_would_not_run` (plain, `partial` and async, every mode, `run` and `with_timeout`), `test_rejects_an_async_generator_returned_by_the_call` |
| b | F4 | low | Thread mode is limited by the GIL switch interval, not the clock, and returned values from calls that ended after their budget | GUIDE states the limit; thread mode records when the call ended and treats an end after the deadline as a timeout, as process mode does | `test_thread.py::test_a_value_that_arrives_after_the_budget_is_a_timeout` |
| a | A2 | low | `run` and `with_timeout` showed and pickled as `calltimeout._api` and `calltimeout._decorator` | Both relabelled `calltimeout` in `__init__.py` | `test_contract_api.py::test_public_objects_live_under_the_package_name` (every public name, and a stored `partial(run, ...)`) |
| a | A3 | low | `CallCrashed.exitcode` was typed `int \| None` and never `None` | Typed `int` (the raise site casts the code of a child that has exited) | `test_typing.py` (revealed type `int`); `test_errors.py` and `test_contract_api.py` build it with codes only |
| c | C4 | low | `RemoteTraceback` built with a text that is not a `str` could not be shown | Its `args` and `str()` show such a text bounded; `.text` keeps it as given | `test_errors.py::test_a_remote_traceback_always_shows_whatever_text_it_was_given` (eight kinds: `str`, `repr`, printed traceback, pickle) |
| a | A4 | low | CONTRIBUTING claimed tests never touch real time or disk; requirements-dev.txt left out pytest-timeout | Both reworded | docs |
| e | F1-N21 | low | Thread mode passing on `SystemExit` and `KeyboardInterrupt` unpinned | | `test_thread.py::test_an_exit_or_interrupt_raised_by_the_call_reaches_the_caller_unchanged` |
| e | F2-N23 | low | A decorated call inside another call's child getting its own child and budget unpinned | | `test_child_outcomes.py::test_a_decorated_call_inside_another_calls_child_gets_its_own_child_and_budget` |
| e | F3-N38 | low | The child's name for a classmethod sent through its class unpinned | | `test_child_outcomes.py::test_a_classmethod_sent_through_its_class_names_the_child_after_the_method` |
| e | F4-N35 | low | The `<note>` stand-in for a note that is not text unpinned | | `test_bounded_causes.py::test_a_note_that_is_not_text_is_replaced_by_a_short_stand_in` and `test_notes_are_kept_bounded_whatever_they_were_set_to` |
| e | F5-N30 | low | The stand-in's `module.qualname` text unpinned | | `test_child_outcomes.py::test_a_stand_in_names_the_type_by_module_and_qualname_even_if_name_is_refused` |
| e | F6-N17 | low | The exact `<unnamed type>` text unpinned | | `test_hostile_names.py::test_every_argument_check_names_a_hostile_type_briefly` (the exact message for a raising and a non-text name) |
| e | F7-N02 | low | A huge `Real` whose comparison raises unpinned | | `test_validation.py::test_a_real_too_large_whose_comparison_fails_is_reported_above_the_limit` |
| e | F8-N34 | low | Notes given as one `str` unpinned on Python 3.14, whose pickle replaces such an error | | `test_bounded_causes.py::test_notes_are_kept_bounded_whatever_they_were_set_to` (on the bounding itself) |

Lens b's entry PASSED records the claims that held and is not a defect. Lens e's
BLOCKED-POSIX entry is not a library finding: its POSIX leg could not get a turn. Its
signal mutants N43 to N55 were written against the `_signal.py` of ebcc8c1, which this
round rewrote (the timer bookkeeping moved to `_timers.py`), so they need writing again
against the new module in the re-verification round; N25 still applies as written.

Mutants, each applied alone: lens e's eight survivors (N23 now in `_child.py`) all
killed on Windows; on this round's fixes G1 to G3 (each kind of deferred function), L1
(no late check), R1 (no rebuild check), U1 (raw load error), P1 and P2 (private module
names), T1 and T2 (raw `RemoteTraceback` text) killed on Windows; W1 (no late flag) and
W2 (no terminate) killed under forkserver and fork, and W3 (no kill) hangs the
stopped-child contract; on the signal fix S1 (no kept schedule), S2 (no settle), S3 (no
hold before the timer is set) and S4 (a foreign tick dropped) each killed by
`test_signal_races.py` under WSL.

The reviewers' own repros on the fix: lens b's `f1b_after.py` keeps the caller's handler
(500 ticks in the next 0.5 s), `f2_lost_deadline.py` ends 300 of 300 trials with
`CallTimeout` at both naps, `e2e_gaps.py` sees 300 of 300 ticks with no odd gap in both
shapes, `e2d_drift.py` stays under 0.2 ms late over 6 s, and `f3_oneshot_drift.py` fires
at 1.0006 s after 89,105 calls; lens c's `stall_probe.py` raises `CallTimeout` at 2.0 s
under each start method, `sigstop_probe.py` ends at the deadline plus the grace period
for every delay that stops the child mid-transfer, and `probe_reduce.py`, `guarded.py`,
`guarded_huge.py` and `ctor_probe.py` give the documented errors, bounded; lens a's
`probe_gen.py` is refused with the generator `TypeError`.

Verification:

- Elena's PC, CPython 3.14.2, fresh clone of e2db93d from GitHub (an `auto:cpu` turn):
  `ruff format --check .`, `ruff check .`, `mypy --strict src`, `mypy --strict src tests`
  and `pytest` each exit 0 (POSIX-only, fork-only, opt-in e2e and fetched-document tests
  skip there). be35644 changes only a POSIX-only contract.
- This PC, at be35644: the static gates exit 0 (CPython 3.13.2, ruff 0.17.0, mypy 2.4.0,
  `mypy --strict src tests` for the Windows and Linux platforms), and the changed test
  files pass on CPython 3.13.2.
- WSL Ubuntu, CPython 3.14.4, working tree at be35644: every signal test file passes
  (44 tests), and the changed process, thread, validation and error test files pass under
  forkserver, fork and spawn.
- The new contracts on the src of ebcc8c1, Windows 3.13.2: 23 fail (every contract above
  except lens e's, which pin behaviour ebcc8c1 already had and are checked by mutants),
  plus `test_a_reader_cut_short_counts_as_no_result`, whose call matches the new private
  signature; on WSL all seven of `test_signal_races.py` fail.

