"""Process and signal facts from the CPython documentation and PEP 475, checked live.

Each test finds the sentence in the fetched document (see tests/_upstream.py), then shows
the interpreter really behaves that way and that calltimeout follows from it.
"""

from __future__ import annotations

import multiprocessing
import os
import re
import sys
import threading
import time

import _targets
import pytest
from _upstream import our_docs, says

from calltimeout import CallCrashed, CallTimeout, run

posix_only = pytest.mark.skipif(sys.platform == "win32", reason="SIGALRM is POSIX")


def test_the_crash_exit_code_is_the_one_multiprocessing_reports() -> None:
    says(
        "cpython-multiprocessing.rst",
        """If it terminated via :func:`sys.exit` with an integer argument *N*, the exit
        code will be *N*.""",
    )
    says(
        "cpython-multiprocessing.rst",
        "If it was terminated by signal *N*, the exit code will be the negative value *-N*.",
    )
    for code in (0, 3, 200):
        plain = multiprocessing.Process(target=os._exit, args=(code,))
        plain.start()
        plain.join(30)
        with pytest.raises(CallCrashed) as info:
            run(os._exit, 30.0, args=(code,), mode="process")
        assert info.value.exitcode == plain.exitcode == code


@posix_only
def test_a_child_killed_by_a_signal_has_a_negative_exit_code() -> None:
    with pytest.raises(CallCrashed) as info:
        run(_targets.kill_self, 30.0, args=(9,), mode="process")
    assert info.value.exitcode == -9


def test_terminate_leaves_descendants_alone_as_the_docs_say() -> None:
    says(
        "cpython-multiprocessing.rst",
        """Note that descendant processes of the process will *not* be terminated --
        they will simply become orphaned.""",
    )
    assert "Processes started by the call itself are not stopped with it." in our_docs()


def test_only_the_main_thread_may_set_a_handler_so_signal_mode_refuses_others() -> None:
    says(
        "cpython-signal.rst",
        "only the main thread of the main interpreter is allowed to set a new signal handler.",
    )
    seen: list[BaseException] = []

    def elsewhere() -> None:
        try:
            run(_targets.echo, 1.0, args=(1,), mode="signal")
        except BaseException as exc:
            seen.append(exc)

    worker = threading.Thread(target=elsewhere)
    worker.start()
    worker.join(30)
    expected = NotImplementedError if sys.platform == "win32" else RuntimeError
    assert type(seen[0]) is expected


def test_a_handler_not_installed_from_python_reads_as_none() -> None:
    says(
        "cpython-signal.rst",
        """``None`` means that the previous signal handler was not installed from
        Python.""",
    )
    says(
        "cpython-signal.rst",
        "The interval timer specified by *which* can be cleared by setting *seconds* to zero.",
    )
    says(
        "cpython-signal.rst",
        "Decrements interval timer in real time, and delivers :const:`SIGALRM` upon expiration.",
    )


def test_a_long_calculation_in_c_is_interrupted_only_once_it_returns() -> None:
    says(
        "cpython-signal.rst",
        """A long-running calculation implemented purely in C (such as regular expression
        matching on a large body of text) may run uninterrupted for an arbitrary amount
        of time, regardless of any signals received. The Python signal handlers will be
        called when the calculation finishes.""",
    )
    assert "A long call inside C: once it returns" in our_docs()


@posix_only
def test_a_raising_handler_stops_a_blocking_system_call() -> None:
    says(
        "pep-0475.rst",
        """If the signal handler raises an exception, the Python wrapper bails out and
        fails with the exception.""",
    )
    started = time.monotonic()
    with pytest.raises(CallTimeout):
        run(time.sleep, 0.2, args=(30,), mode="signal")
    assert time.monotonic() - started < 10


def test_the_docs_ask_for_the_main_module_guard_multiprocessing_needs() -> None:
    says("cpython-multiprocessing.rst", "Safe importing of main module")
    says(
        "cpython-multiprocessing.rst",
        """A numeric handle of a system object which will become "ready" when the process
        ends.""",
    )
    assert re.search(r'if __name__ == "__main__":', our_docs())
