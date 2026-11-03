# QA findings and verification

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

