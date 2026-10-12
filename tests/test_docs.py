"""The README examples run and print what their comments say; metadata agrees."""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

import calltimeout

ROOT = Path(__file__).resolve().parents[1]

TRANSCRIPT = [
    "payload",
    "gave up after 0.05 seconds",
    "cached",
    "5",
    "None",
    "2432902008176640000",
    "stopped",
    "exit code 3",
    "interrupted: CallTimeout",
    "stopped",
]
POSIX_ONLY = {"interrupted: CallTimeout"}


def _expected() -> list[str]:
    if sys.platform == "win32":
        return [line for line in TRANSCRIPT if line not in POSIX_ONLY]
    return TRANSCRIPT


def _readme() -> str:
    return (ROOT / "README.md").read_text(encoding="utf-8")


def _python_blocks() -> list[str]:
    return re.findall(r"```python\n(.*?)```", _readme(), flags=re.DOTALL)


def test_every_readme_example_runs_and_prints_the_transcript(
    capsys: pytest.CaptureFixture[str],
) -> None:
    blocks = _python_blocks()
    assert len(blocks) == 5
    for block in blocks:
        exec(compile(block, "README.md", "exec"), {"__name__": "readme"})
    assert capsys.readouterr().out.splitlines() == _expected()


def test_every_printed_comment_is_real_output() -> None:
    # "print(...)  # value" promises a line of output; a stale comment fails here.
    comments = [
        line.split("  # ", 1)[1]
        for block in _python_blocks()
        for line in block.splitlines()
        if line.lstrip().startswith("print(") and "  # " in line
    ]
    assert comments == TRANSCRIPT


def test_every_public_name_appears_in_the_readme() -> None:
    for name in calltimeout.__all__:
        assert name in _readme(), name


def test_version_matches_pyproject() -> None:
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version = "([^"]+)"$', text, flags=re.MULTILINE)
    assert match is not None
    assert match.group(1) == calltimeout.__version__


def test_changelog_has_an_entry_for_this_version() -> None:
    text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert f"## [{calltimeout.__version__}]" in text


def test_the_grace_period_in_the_readme_matches_the_code() -> None:
    from calltimeout import _process

    assert f"killed if still alive {_process.GRACE:g} second later" in _readme()
