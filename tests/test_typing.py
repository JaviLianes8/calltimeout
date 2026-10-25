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
from fractions import Fraction
reveal_type(run(scale, Fraction(1, 2), args=(3,)))
reveal_type(with_timeout(Fraction(1, 2))(scale)(3))
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
        (18, "float"),
        (19, "float"),
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


@pytest.mark.parametrize("platform", ["win32", "linux"])
def test_every_documented_example_passes_strict_type_checking(
    platform: str, tmp_path: Path
) -> None:
    files: list[str] = []
    for doc in ("README.md", "GUIDE.md"):
        text = (SRC.parent / doc).read_text(encoding="utf-8")
        for number, block in enumerate(re.findall(r"```python\n(.*?)```", text, re.DOTALL)):
            example = tmp_path / f"{doc.split('.')[0].lower()}_{number}.py"
            example.write_text(block, encoding="utf-8")
            files.append(str(example))
    config = tmp_path / "mypy.ini"
    config.write_text(f"[mypy]\nmypy_path = {SRC.as_posix()}\n", encoding="utf-8")
    cache = str(tmp_path / "cache")
    options = ["--strict", "--platform", platform, "--config-file", str(config)]
    out, err, status = api.run([*options, "--cache-dir", cache, *files])
    assert status == 0, str(out) + str(err)
    assert len(files) == 7
