"""Inject each deliberate bug listed in scripts/mutants.json and check the suite catches it.

Every mutant replaces one exact piece of code (which must occur once), runs the suite with
-x, records the first failing test and restores the file, also on errors. A mutant the
suite does not catch is a missing contract. Mutants marked "posix" need SIGALRM and are
skipped on Windows. Prints one Markdown table row per mutant.

    python scripts/mutate.py [first-id] [last-id]
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MUTANTS = json.loads((ROOT / "scripts" / "mutants.json").read_text(encoding="utf-8"))


def _suite(basetemp: str) -> tuple[bool, str]:
    command = [sys.executable, "-m", "pytest", "-x", "-q", "-p", "no:cacheprovider"]
    command += ["-o", "addopts=--doctest-modules", f"--basetemp={basetemp}", "src", "tests"]
    done = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=900)
    found = re.findall(r"^(?:FAILED|ERROR) (\S+)", done.stdout, flags=re.MULTILINE)
    return done.returncode == 0, found[0] if found else done.stdout[-200:]


def main(first: str = "", last: str = "") -> int:
    survivors = 0
    print("| Id | Mutation | File | Result | Caught by |")
    print("| --- | --- | --- | --- | --- |")
    for mutant in MUTANTS:
        if (first and mutant["id"] < first) or (last and mutant["id"] > last):
            continue
        path = ROOT / mutant["file"]
        row = f"| {mutant['id']} | {mutant['what']} | `{mutant['file']}` |"
        if mutant.get("posix") and sys.platform == "win32":
            print(f"{row} POSIX run | |")
            continue
        original = path.read_bytes()
        text = original.decode("utf-8")
        newline = "\r\n" if "\r\n" in text else "\n"
        old, new = (mutant[key].replace("\n", newline) for key in ("old", "new"))
        if text.count(old) != 1:
            print(f"{row} BAD MUTANT | |")
            survivors += 1
            continue
        try:
            path.write_bytes(text.replace(old, new).encode("utf-8"))
            with tempfile.TemporaryDirectory(dir=os.environ.get("MUTATE_TMP")) as basetemp:
                passed, caught = _suite(basetemp)
        finally:
            path.write_bytes(original)
        survivors += passed
        print(f"{row} SURVIVED | |" if passed else f"{row} killed | `{caught}` |")
        sys.stdout.flush()
    return 1 if survivors else 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:3]))
