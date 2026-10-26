"""Names and texts that lie about their length, or raise when read, give bounded typed errors."""

from __future__ import annotations

import multiprocessing
import pickle
import threading
from collections.abc import Callable

import _hostile_errors
import pytest

from calltimeout import CallCrashed, CallTimeout, Mode, run

LONG = "SECRET-" + "N" * 1_000_000

FORK = multiprocessing.get_start_method() == "fork"


def _lying_type() -> type:
    class Named:
        pass

    Named.__name__ = _hostile_errors.LyingStr(LONG)
    return Named


class _RaisingName(type):
    @property
    def __name__(cls) -> str:  # type: ignore[override]
        raise ZeroDivisionError("name refused")


class _NumberName(type):
    @property
    def __name__(cls) -> object:  # type: ignore[override]
        return 7


def _unnamed() -> object:
    # Made on demand: pytest reads the name of every class it finds in a test module.
    class Unnamed(metaclass=_RaisingName):
        pass

    return Unnamed()


def _numbered() -> object:
    class Numbered(metaclass=_NumberName):
        pass

    return Numbered()


class _Anonymous(metaclass=_hostile_errors.QualMeta):
    """A callable whose type refuses its qualified name; it has none of its own."""

    def __call__(self) -> str:
        return threading.current_thread().name


def _thread_name() -> str:
    return threading.current_thread().name


_thread_name.__qualname__ = _hostile_errors.LyingStr(LONG)


async def _coroutine() -> None:
    return None


_coroutine.__qualname__ = _hostile_errors.LyingStr(LONG)


class _LyingFloat(float):
    def __str__(self) -> str:
        return _hostile_errors.LyingStr(LONG)


class _LyingInt(int):
    def __str__(self) -> str:
        return _hostile_errors.LyingStr(LONG)


CHECKS: dict[str, tuple[Callable[[object], object], str]] = {
    "timeout": (lambda bad: run(print, bad), "timeout must be a number of seconds, not "),  # type: ignore[call-overload]
    "args": (lambda bad: run(print, 1.0, args=bad), "args must be a tuple, not "),  # type: ignore[call-overload]
    "kwargs": (lambda bad: run(print, 1.0, kwargs=bad), "kwargs must be a mapping, not "),  # type: ignore[call-overload]
    "mode": (lambda bad: run(print, 1.0, mode=bad), "mode must be a str, not "),  # type: ignore[call-overload]
    "fn": (lambda bad: run(bad, 1.0), "fn must be callable, not "),  # type: ignore[call-overload]
}


@pytest.mark.parametrize("check", CHECKS.values(), ids=CHECKS.keys())
@pytest.mark.parametrize(
    "make", [lambda: _lying_type()(), _unnamed, _numbered], ids=["lying", "raising", "number"]
)
def test_every_argument_check_names_a_hostile_type_briefly(
    check: tuple[Callable[[object], object], str], make: Callable[[], object]
) -> None:
    call, message = check
    with pytest.raises(TypeError) as info:
        call(make())
    assert str(info.value).startswith(message)
    assert len(str(info.value)) < 200
    assert info.value.__cause__ is None


def test_a_function_name_that_lies_about_its_length_is_cut() -> None:
    name = run(_thread_name, 30.0)
    assert name.startswith("calltimeout:SECRET-NNN")
    assert len(name) < 100
    with pytest.raises(TypeError, match="coroutine function") as info:
        _ = run(_coroutine, 30.0)
    assert len(str(info.value)) < 300


def test_a_callable_whose_type_refuses_its_name_still_runs() -> None:
    assert run(_Anonymous(), 30.0).startswith("calltimeout:")
    if FORK:
        assert run(_Anonymous(), 30.0, mode="process").startswith("calltimeout:")
    else:
        with pytest.raises(pickle.PicklingError, match="cannot be sent"):
            run(_Anonymous(), 30.0, mode="process")


def test_numbers_whose_text_lies_about_its_length_are_cut() -> None:
    assert len(str(CallTimeout(_LyingFloat(1.5)))) < 200
    assert len(str(CallCrashed(_LyingInt(3)))) < 200


def test_an_unpicklable_child_error_with_a_lying_text_is_named_briefly() -> None:
    with pytest.raises(RuntimeError, match="LyingUnpicklable") as info:
        run(_hostile_errors.raise_lying_unpicklable, 30.0, mode="process")
    assert len(str(info.value)) < 1000


@pytest.mark.parametrize("mode", ["thread", "process"])
def test_a_child_error_whose_type_refuses_its_module_still_arrives(mode: Mode) -> None:
    # Its traceback cannot be formatted nor its type pickled: the child still sends a
    # stand-in naming it, never a crash.
    expected = _hostile_errors.ModuleErr if mode == "thread" else RuntimeError
    with pytest.raises(expected) as info:
        run(_hostile_errors.raise_module_err, 30.0, mode=mode)
    assert not isinstance(info.value, CallCrashed)
    assert "boom" in str(info.value)
    assert len(str(info.value)) < 1000
