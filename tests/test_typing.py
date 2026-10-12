"""The public API is typed: mypy infers results, keeps signatures, rejects bad calls."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

api = pytest.importorskip("mypy.api")

SRC = Path(__file__).resolve().parents[1] / "src"

SNIPPET = """
from calltimeout import run, with_timeout


def scale(value: int, factor: float = 2.0) -> float:
    return value * factor


reveal_type(run(scale, 1.0, args=(3,)))
reveal_type(run(scale, 1.0, args=(3,), default=None))
reveal_type(with_timeout(1.0)(scale))
reveal_type(with_timeout(1.0, mode="process", default="late")(scale)(3))
with_timeout(1.0)(scale)("3")
with_timeout(1.0)(scale)(3, bogus=1)
run(scale, "1.0")
with_timeout(1.0, mode="fiber")
"""


@pytest.fixture(scope="module")
def mypy_output(tmp_path_factory: pytest.TempPathFactory) -> str:
    folder = tmp_path_factory.mktemp("typing")
    target = folder / "snippet.py"
    target.write_text(SNIPPET, encoding="utf-8")
    config = folder / "mypy.ini"
    config.write_text(f"[mypy]\nmypy_path = {SRC.as_posix()}\n", encoding="utf-8")
    cache = str(folder / "cache")
    out, err, _ = api.run(
        ["--strict", "--config-file", str(config), "--cache-dir", cache, str(target)]
    )
    return str(out) + str(err)


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        (9, "float"),
        (10, "float | None"),
        (11, "def (value: int, factor: float =) -> float"),
        (12, "float | str"),
    ],
)
def test_results_and_signatures_are_typed(mypy_output: str, line: int, expected: str) -> None:
    match = re.search(rf"snippet\.py:{line}: note: Revealed type is \"(.+)\"", mypy_output)
    assert match, mypy_output
    # Older mypy releases spell builtins with their module prefix and unions as Union.
    revealed = match.group(1).replace("builtins.", "")
    revealed = re.sub(r"Union\[(.+), None\]", r"\1 | None", revealed)
    revealed = re.sub(r"Union\[(\w+), (\w+)\]", r"\1 | \2", revealed)
    assert revealed == expected


@pytest.mark.parametrize(
    ("line", "code"),
    [(13, "arg-type"), (14, "call-arg"), (15, "call-overload"), (16, "call-overload")],
)
def test_wrong_calls_are_rejected(mypy_output: str, line: int, code: str) -> None:
    assert re.search(rf"snippet\.py:{line}: error: .*\[{code}\]", mypy_output), mypy_output
