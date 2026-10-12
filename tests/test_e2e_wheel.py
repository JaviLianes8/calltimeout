"""Build the wheel, install it in a throwaway venv and drive the installed package.

Slow and needs the build backend, so it runs only with CALLTIMEOUT_E2E=1.
"""

from __future__ import annotations

import os
import subprocess
import sys
import venv
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

pytestmark = pytest.mark.skipif(
    os.environ.get("CALLTIMEOUT_E2E") != "1", reason="set CALLTIMEOUT_E2E=1 to build and install"
)

# A script, not "-c": process mode must re-import the entry point under spawn.
PROGRAM = r"""
import importlib.metadata, importlib.resources, os, sys, time
import calltimeout
from calltimeout import CallCrashed, CallTimeout, run, with_timeout


@with_timeout(30.0, mode="process")
def child_pid(offset: int) -> int:
    return os.getpid() + offset


@with_timeout(0.5, mode="process", default="stopped")
def runaway() -> str:
    time.sleep(60)
    return "finished"


def explode() -> None:
    raise KeyError("missing")


if __name__ == "__main__":
    assert "site-packages" in calltimeout.__file__, calltimeout.__file__
    assert importlib.metadata.version("calltimeout") == calltimeout.__version__
    assert importlib.resources.files("calltimeout").joinpath("py.typed").is_file()

    assert run(pow, 5.0, args=(2, 10)) == 1024
    assert run(time.sleep, 0.05, args=(1.0,), default="late") == "late"
    assert child_pid(0) != os.getpid()
    started = time.monotonic()
    assert runaway() == "stopped"
    assert time.monotonic() - started < 10
    try:
        run(os._exit, 30.0, args=(7,), mode="process")
    except CallCrashed as exc:
        assert exc.exitcode == 7
    else:
        raise AssertionError("crash not reported")
    try:
        run(explode, 30.0, mode="process")
    except KeyError as exc:
        assert "raise KeyError" in str(exc.__cause__)
    else:
        raise AssertionError("child error not raised")
    if sys.platform != "win32":
        try:
            run(time.sleep, 0.1, args=(60,), mode="signal")
        except CallTimeout as exc:
            assert exc.timeout == 0.1
        else:
            raise AssertionError("signal mode did not interrupt")
    print("e2e ok")
"""


def _run(*cmd: str | Path, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(c) for c in cmd], cwd=cwd, capture_output=True, text=True, check=False
    )


def test_installed_wheel_end_to_end(tmp_path: Path) -> None:
    dist = tmp_path / "dist"
    built = _run(sys.executable, "-m", "build", "--wheel", "--outdir", dist, ROOT)
    assert built.returncode == 0, built.stderr
    (wheel,) = dist.glob("calltimeout-*.whl")

    env_dir = tmp_path / "venv"
    venv.create(env_dir, with_pip=True)
    bindir = env_dir / ("Scripts" if sys.platform == "win32" else "bin")
    python = bindir / "python"
    installed = _run(python, "-m", "pip", "install", "-q", wheel)
    assert installed.returncode == 0, installed.stderr

    # Run from an empty folder so the source tree cannot shadow the install.
    work = tmp_path / "work"
    work.mkdir()
    script = work / "program.py"
    script.write_text(PROGRAM, encoding="utf-8")
    result = _run(python, "-I", script, cwd=work)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "e2e ok"
