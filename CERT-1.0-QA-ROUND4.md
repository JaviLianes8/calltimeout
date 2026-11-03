# QA findings and verification

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

