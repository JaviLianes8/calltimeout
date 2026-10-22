"""Build the wheel and sdist, inspect them, install each in a throwaway venv and use it.

Slow and needs the build backend, so it runs only with CALLTIMEOUT_E2E=1. It builds from
this source tree, or takes ready-made files from CALLTIMEOUT_WHEEL and CALLTIMEOUT_SDIST
(so it also runs from an unpacked sdist without src).
"""

from __future__ import annotations

import email
import importlib.util
import os
import subprocess
import sys
import tarfile
import venv
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULES = ["__init__", "_api", "_decorator", "_errors", "_process", "_signal", "_text"]
MODULES += ["_thread", "_validate", "_wire"]
PACKAGE = {f"calltimeout/{name}.py" for name in MODULES} | {"calltimeout/py.typed"}

pytestmark = pytest.mark.skipif(
    os.environ.get("CALLTIMEOUT_E2E") != "1", reason="set CALLTIMEOUT_E2E=1 to build and install"
)


def _run(*cmd: str | Path, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(c) for c in cmd], cwd=cwd, capture_output=True, text=True, check=False
    )


@pytest.fixture(scope="module")
def dists(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path]:
    given = os.environ.get("CALLTIMEOUT_WHEEL"), os.environ.get("CALLTIMEOUT_SDIST")
    if given[0] and given[1]:
        return Path(given[0]), Path(given[1])
    if not (ROOT / "src").is_dir():
        pytest.skip("no source tree: set CALLTIMEOUT_WHEEL and CALLTIMEOUT_SDIST")
    out = tmp_path_factory.mktemp("dist")
    built = _run(sys.executable, "-m", "build", "--sdist", "--wheel", "--outdir", out, ROOT)
    assert built.returncode == 0, built.stderr
    (wheel,) = out.glob("calltimeout-*.whl")
    (sdist,) = out.glob("calltimeout-*.tar.gz")
    return wheel, sdist


def _venv(where: Path) -> Path:
    venv.create(where, with_pip=True)
    return where / ("Scripts" if sys.platform == "win32" else "bin") / "python"


def _use(python: Path, work: Path) -> None:
    # From an empty folder with -I, so no source tree can shadow the install.
    work.mkdir()
    script = work / "consumer.py"
    script.write_text((Path(__file__).parent / "_consumer.py").read_text(encoding="utf-8"))
    result = _run(python, "-I", script, cwd=work)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "e2e ok"


def test_the_wheel_holds_the_package_license_and_honest_metadata(dists: tuple[Path, Path]) -> None:
    wheel, _ = dists
    with zipfile.ZipFile(wheel) as archive:
        names = set(archive.namelist())
        info = "calltimeout-1.0.0.dist-info/"
        assert names - PACKAGE == {info + n for n in ("METADATA", "RECORD", "WHEEL")} | {
            info + "licenses/LICENSE"
        }
        meta = email.message_from_bytes(archive.read(info + "METADATA"))
    assert meta["Version"] == "1.0.0"
    assert meta["Requires-Python"] == ">=3.10"
    assert meta["License-Expression"] == "MIT"
    assert not [r for r in meta.get_all("Requires-Dist") or [] if "extra ==" not in r]
    classifiers = meta.get_all("Classifier") or []
    assert "Development Status :: 5 - Production/Stable" in classifiers
    versions = [c.rsplit(" ", 1)[1] for c in classifiers if c.startswith("Programming Language")]
    assert [v for v in versions if v.count(".") == 1] == ["3.10", "3.11", "3.12", "3.13", "3.14"]
    urls = {u.split(",")[0] for u in meta.get_all("Project-URL") or []}
    assert {"Homepage", "Source", "Issues", "Changelog"} <= urls


def test_the_sdist_ships_sources_tests_and_docs_but_no_fetched_documents(
    dists: tuple[Path, Path],
) -> None:
    _, sdist = dists
    with tarfile.open(sdist) as archive:
        names = {n.split("/", 1)[1] for n in archive.getnames() if "/" in n}
    assert {f"src/{n}" for n in PACKAGE} <= names
    assert {"LICENSE", "README.md", "GUIDE.md", "CHANGELOG.md", "pyproject.toml"} <= names
    assert {"tests/upstream/MANIFEST.json", "tests/_consumer.py", "tests/conftest.py"} <= names
    assert not [n for n in names if n.startswith("tests/upstream/") and n.endswith(".rst")]
    assert not [n for n in names if "__pycache__" in n or n.endswith(".pyc")]
    assert not [n for n in names if n.startswith(("IMPROVEMENTS", "CERT-1.0", "dist/"))]


@pytest.mark.skipif(importlib.util.find_spec("twine") is None, reason="needs twine")
def test_twine_accepts_both_files(dists: tuple[Path, Path]) -> None:
    checked = _run(sys.executable, "-m", "twine", "check", "--strict", *dists)
    assert checked.returncode == 0, checked.stdout + checked.stderr


def test_the_installed_wheel_works_for_a_consumer(dists: tuple[Path, Path], tmp_path: Path) -> None:
    python = _venv(tmp_path / "venv")
    installed = _run(python, "-m", "pip", "install", "-q", dists[0])
    assert installed.returncode == 0, installed.stderr
    _use(python, tmp_path / "work")
    if importlib.util.find_spec("mypy") is not None:
        consumer = tmp_path / "work" / "consumer.py"
        typed = _run(
            sys.executable,
            "-m",
            "mypy",
            "--strict",
            "--python-executable",
            python,
            "--cache-dir",
            tmp_path / "cache",
            consumer,
        )
        assert typed.returncode == 0, typed.stdout


def test_the_sdist_installs_and_works_too(dists: tuple[Path, Path], tmp_path: Path) -> None:
    python = _venv(tmp_path / "venv")
    installed = _run(python, "-m", "pip", "install", "-q", dists[1])
    assert installed.returncode == 0, installed.stderr
    _use(python, tmp_path / "work")
