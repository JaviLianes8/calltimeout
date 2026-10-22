"""Thread, asyncio, inspect and pickle facts from the CPython documentation, checked live.

Each test finds the sentence in the fetched document (see tests/_upstream.py), then shows
the interpreter really behaves that way and that calltimeout follows from it.
"""

from __future__ import annotations

import asyncio
import contextvars
import functools
import sys
import threading

import _targets
import pytest
from _upstream import document, says

from calltimeout import CallTimeout, run


def test_a_timeout_above_timeout_max_is_refused_before_any_wait() -> None:
    says(
        "cpython-threading.rst",
        """Specifying a timeout greater than this value will raise an
        :exc:`OverflowError`.""",
    )
    with pytest.raises(OverflowError):
        threading.Lock().acquire(timeout=threading.TIMEOUT_MAX * 2)
    with pytest.raises(ValueError, match="at most"):
        run(_targets.echo, threading.TIMEOUT_MAX * 2, args=(1,))
    assert run(_targets.echo, threading.TIMEOUT_MAX, args=(1,)) == 1


def test_join_says_nothing_about_a_timeout_so_is_alive_decides() -> None:
    says(
        "cpython-threading.rst",
        """As :meth:`~Thread.join` always returns ``None``, you must call
        :meth:`~Thread.is_alive` after :meth:`~Thread.join` to decide whether a timeout
        happened""",
    )
    event = threading.Event()
    worker = threading.Thread(target=event.wait, daemon=True)
    worker.start()
    returned: object = worker.join(0.01)  # type: ignore[func-returns-value]
    assert returned is None
    assert worker.is_alive()
    event.set()
    with pytest.raises(CallTimeout):
        run(_targets.blocks_until_gate, 0.05)
    _targets.gate.set()


def test_a_lingering_call_runs_in_a_daemon_thread() -> None:
    says("cpython-threading.rst", "Daemon threads are abruptly stopped at shutdown.")
    release = threading.Event()
    with pytest.raises(CallTimeout):
        run(release.wait, 0.05, args=(30.0,))
    (worker,) = [t for t in threading.enumerate() if t.name == "calltimeout:Event.wait"]
    assert worker.daemon
    release.set()


def test_the_coroutine_hint_matches_what_each_python_offers() -> None:
    text = document("cpython-asyncio-task.rst")
    timeout_section = text.split(".. function:: timeout(delay)")[1].split(".. function::")[0]
    assert ".. versionadded:: 3.11" in timeout_section
    old = document("cpython-3.10-asyncio-task.rst")
    assert ".. function:: timeout(" not in old
    assert ".. coroutinefunction:: wait_for(aw, timeout)" in old
    assert hasattr(asyncio, "timeout") == (sys.version_info >= (3, 11))
    assert hasattr(asyncio, "wait_for")

    async def job() -> None:
        return None

    with pytest.raises(TypeError, match=r"asyncio\.timeout\(\) \(Python 3\.11\+\)"):
        _ = run(job, 1.0)


def test_a_partial_of_a_coroutine_function_is_refused_without_its_arguments() -> None:
    says(
        "cpython-inspect.rst",
        """a :func:`functools.partial` wrapping a :term:`coroutine function`""",
    )

    async def login(password: str) -> str:
        return password

    bound = functools.partial(login, "hunter2-secret")
    with pytest.raises(TypeError) as info:
        _ = run(bound, 1.0)
    assert "hunter2" not in str(info.value)
    assert str(info.value).startswith("partial is a coroutine function")


VAR: contextvars.ContextVar[str] = contextvars.ContextVar("VAR", default="unset")


def test_thread_mode_sees_context_variables_as_asyncio_to_thread_does() -> None:
    says(
        "cpython-asyncio-task.rst",
        """Also, the current :class:`contextvars.Context` is propagated, allowing context
        variables from the event loop thread to be accessed in the separate thread.""",
    )

    async def through_asyncio() -> str:
        VAR.set("caller")
        return await asyncio.to_thread(VAR.get)

    def through_run() -> str:
        VAR.set("caller")
        return run(VAR.get, 30.0)

    assert asyncio.run(through_asyncio()) == contextvars.Context().run(through_run) == "caller"


def test_the_exceptions_pickle_their_state_the_documented_way() -> None:
    says(
        "cpython-pickle.rst",
        """If the object has no such method then, the value must be a dictionary and it
        will be added to the object's :attr:`~object.__dict__` attribute.""",
    )
    error = CallTimeout(0.5)
    error.extra = 1  # type: ignore[attr-defined]
    rebuild, arguments, state = error.__reduce__()
    assert (rebuild, arguments, state) == (CallTimeout, (0.5,), {"timeout": 0.5, "extra": 1})
