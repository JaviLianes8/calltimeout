"""The README and GUIDE examples run and print what their comments say; metadata agrees."""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

import calltimeout

ROOT = Path(__file__).resolve().parents[1]
DOCS = ["README.md", "GUIDE.md"]

# Lines printed only where signal mode exists.
POSIX_ONLY = {"interrupted: CallTimeout"}


def _text(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8")


def _python_blocks(name: str) -> list[str]:
    return re.findall(r"```python\n(.*?)```", _text(name), flags=re.DOTALL)


def _promised(name: str) -> list[str]:
    # "print(...)  # value" promises a line of output.
    return [
        line.split("  # ", 1)[1]
        for block in _python_blocks(name)
        for line in block.splitlines()
        if line.lstrip().startswith("print(") and "  # " in line
    ]


@pytest.mark.parametrize(("name", "blocks"), [("README.md", 2), ("GUIDE.md", 5)])
def test_every_example_runs_as_a_script_and_prints_what_its_comments_say(
    name: str, blocks: int, tmp_path: Path
) -> None:
    # Each block is saved and run as "python example.py", the way a reader runs it, so
    # spawn and forkserver re-import it as the main module like any script.
    found = _python_blocks(name)
    assert len(found) == blocks
    env = {**os.environ, "PYTHONPATH": str(Path(calltimeout.__file__).resolve().parents[1])}
    printed: list[str] = []
    for number, block in enumerate(found):
        script = tmp_path / f"example_{number}.py"
        script.write_text(block, encoding="utf-8")
        done = subprocess.run(
            [sys.executable, str(script)],
            cwd=tmp_path,
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert done.returncode == 0, (name, number, done.stderr)
        printed += done.stdout.splitlines()
    expected = _promised(name)
    if sys.platform == "win32":
        expected = [line for line in expected if line not in POSIX_ONLY]
    assert printed == expected
    assert len(expected) >= 2


@pytest.mark.parametrize("name", DOCS)
def test_every_process_example_guards_its_entry_point(name: str) -> None:
    # Unguarded, it works under fork and crashes under spawn and forkserver.
    for block in _python_blocks(name):
        if 'mode="process"' in block:
            assert '\nif __name__ == "__main__":\n' in block, block


def test_every_public_name_is_documented_in_both_files() -> None:
    for name in DOCS:
        for public in calltimeout.__all__:
            assert public in _text(name), (name, public)


@pytest.mark.parametrize("name", DOCS)
def test_every_link_is_absolute_so_it_works_on_pypi(name: str) -> None:
    targets = re.findall(r"\]\(([^)]+)\)", _text(name))
    assert targets
    assert all(target.startswith("https://") for target in targets), targets


def test_the_readme_carries_the_certified_badge() -> None:
    badge = (
        "[![Lianes8 Certified](https://lianes8studio.com/certified/lianes8-certified-badge.svg)]"
        "(https://lianes8studio.com/certified)"
    )
    assert _text("README.md").splitlines()[2] == badge


def test_version_matches_pyproject() -> None:
    match = re.search(r'^version = "([^"]+)"$', _text("pyproject.toml"), flags=re.MULTILINE)
    assert match is not None
    assert match.group(1) == calltimeout.__version__


def test_the_changelog_has_a_dated_entry_for_this_version() -> None:
    assert re.search(
        rf"^## \[{re.escape(calltimeout.__version__)}\] - \d{{4}}-\d{{2}}-\d{{2}}$",
        _text("CHANGELOG.md"),
        flags=re.MULTILINE,
    )


def test_the_grace_period_in_the_docs_matches_the_code() -> None:
    from calltimeout import _process

    assert f"killed if still alive {_process.GRACE:g} second later" in _text("README.md")
    assert f"killed if it is still alive {_process.GRACE:g} second later" in _text("GUIDE.md")
    assert f"up to {_process.GRACE:g} second to shut down" in _text("GUIDE.md")


def test_the_message_limit_in_the_guide_matches_the_code() -> None:
    from calltimeout import _text as text

    assert f"quote at most {text.LIMIT} characters" in _text("GUIDE.md")
