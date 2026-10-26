"""The 1.0.0 public API, pinned: names, signatures, defaults, types and exception shapes.

Changing anything here is a breaking change and needs a new major version.
"""

from __future__ import annotations

import inspect
import pickle
import typing

import pytest

import calltimeout
from calltimeout import CallCrashed, CallTimeout, Mode, RemoteTraceback, run, with_timeout

KW = inspect.Parameter.KEYWORD_ONLY
POS = inspect.Parameter.POSITIONAL_OR_KEYWORD
EMPTY = inspect.Parameter.empty


def _shape(fn: object) -> list[tuple[str, object, object]]:
    signature = inspect.signature(fn)  # type: ignore[arg-type]
    return [(p.name, p.kind, p.default) for p in signature.parameters.values()]


def test_run_takes_fn_and_timeout_then_keyword_only_options() -> None:
    shape = _shape(run)
    assert shape[:2] == [("fn", POS, EMPTY), ("timeout", POS, EMPTY)]
    assert shape[2:5] == [("args", KW, ()), ("kwargs", KW, None), ("mode", KW, "thread")]
    assert [(name, kind) for name, kind, _ in shape[5:]] == [("default", KW)]
    assert repr(shape[5][2]) == "<no default>"


def test_with_timeout_takes_the_budget_then_keyword_only_options() -> None:
    shape = _shape(with_timeout)
    assert shape[:2] == [("timeout", POS, EMPTY), ("mode", KW, "thread")]
    assert [(name, kind) for name, kind, _ in shape[2:]] == [("default", KW)]


def test_mode_is_the_literal_of_the_three_names() -> None:
    assert typing.get_origin(Mode) is typing.Literal
    assert typing.get_args(Mode) == ("thread", "process", "signal")


def test_the_exceptions_extend_the_builtin_ones_callers_already_catch() -> None:
    assert CallTimeout.__mro__[1:] == TimeoutError.__mro__
    assert CallCrashed.__mro__[1:] == RuntimeError.__mro__
    assert _shape(CallTimeout) == [("timeout", POS, EMPTY)]
    assert _shape(CallCrashed) == [("exitcode", POS, EMPTY)]


@pytest.mark.parametrize(
    ("error", "attribute", "value", "message"),
    [
        (CallTimeout(2.5), "timeout", 2.5, "call did not finish within 2.5 seconds"),
        (CallTimeout(3), "timeout", 3, "call did not finish within 3 seconds"),
        (
            CallCrashed(-9),
            "exitcode",
            -9,
            "the call's process exited with code -9 before returning",
        ),
        (
            CallCrashed(None),
            "exitcode",
            None,
            "the call's process exited with code None before returning",
        ),
    ],
)
def test_each_exception_keeps_its_number_and_states_it(
    error: Exception, attribute: str, value: object, message: str
) -> None:
    assert getattr(error, attribute) == value
    assert str(error) == message
    assert error.args == (message,)


def test_every_public_name_is_documented_with_an_example() -> None:
    for name in calltimeout.__all__:
        if name == "Mode":
            continue  # a typing alias: documented in the package docstring
        doc = inspect.getdoc(getattr(calltimeout, name)) or ""
        assert ">>> " in doc, name
    assert "Mode" in (calltimeout.__doc__ or "")
    assert ">>> " in (calltimeout.__doc__ or "")


def test_remote_traceback_is_an_exception_whose_text_is_the_childs_traceback() -> None:
    assert RemoteTraceback.__mro__[1:] == Exception.__mro__
    assert _shape(RemoteTraceback) == [("text", POS, EMPTY)]
    cause = RemoteTraceback("Traceback (most recent call last):\n  ...\nValueError: x\n")
    assert str(cause) == cause.text == cause.args[0]
    clone = pickle.loads(pickle.dumps(cause))
    assert type(clone) is RemoteTraceback
    assert clone.text == cause.text


def test_public_objects_live_under_the_package_name() -> None:
    assert CallTimeout.__module__ == CallCrashed.__module__ == "calltimeout"
    assert RemoteTraceback.__module__ == "calltimeout"
    for public in (run, with_timeout, CallTimeout, CallCrashed, RemoteTraceback):
        assert pickle.loads(pickle.dumps(public)) is public


def test_the_package_has_no_runtime_dependencies() -> None:
    import importlib.metadata

    try:
        requires = importlib.metadata.requires("calltimeout") or []
    except importlib.metadata.PackageNotFoundError:
        pytest.skip("not installed: the metadata is checked by the e2e test")
    assert [r for r in requires if "extra ==" not in r] == []
