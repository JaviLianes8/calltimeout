import doctest
import importlib.resources
import os
import subprocess
import sys
from pathlib import Path

import calltimeout

# The public API. Add every exported name here as the library grows; this list is the
# contract and the test below fails if the module and this list disagree.
PUBLIC_API: list[str] = [
    "CallCrashed",
    "CallTimeout",
    "Mode",
    "RemoteTraceback",
    "run",
    "with_timeout",
]


def test_all_lists_exactly_the_public_api() -> None:
    assert sorted(calltimeout.__all__) == sorted(PUBLIC_API)


def test_every_exported_name_resolves() -> None:
    for name in calltimeout.__all__:
        assert hasattr(calltimeout, name)


def test_version_is_a_three_part_string() -> None:
    parts = calltimeout.__version__.split(".")
    assert len(parts) == 3
    assert all(part.isdigit() for part in parts)


def test_the_package_ships_type_information() -> None:
    assert importlib.resources.files("calltimeout").joinpath("py.typed").is_file()


def _mode_section() -> str:
    doc = calltimeout.__doc__ or ""
    return doc[doc.index("\nMode\n----\n") :]


def test_mode_is_documented_in_the_package_docstring_with_an_example_that_runs() -> None:
    section = _mode_section()
    test = doctest.DocTestParser().get_doctest(section, {}, "calltimeout.Mode", None, 0)
    runner = doctest.DocTestRunner()
    runner.run(test)
    result = runner.summarize(verbose=False)
    assert result.attempted >= 4
    assert result.failed == 0


def test_importing_the_package_leaves_typings_cached_literal_alone() -> None:
    # Literal[...] is cached: setting Mode.__doc__ relabelled the caller's own aliases.
    code = (
        "from typing import Literal\n"
        "mine = Literal['thread', 'process', 'signal']\n"
        "mine.__doc__ = 'my own alias'\n"
        "import calltimeout\n"
        "print(mine.__doc__)\n"
        "print(Literal['thread', 'process', 'signal'].__doc__)\n"
    )
    path = str(Path(calltimeout.__file__).resolve().parents[1])
    env = {**os.environ, "PYTHONPATH": path}
    done = subprocess.run(
        [sys.executable, "-c", code], env=env, capture_output=True, text=True, timeout=60
    )
    assert done.returncode == 0, done.stderr
    assert done.stdout.splitlines() == ["my own alias", "my own alias"]
