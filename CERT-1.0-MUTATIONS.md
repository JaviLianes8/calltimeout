# Original mutation round

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

