# QA findings and verification

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

