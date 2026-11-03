"""Read the fetched third-party documents in tests/upstream, checked against the manifest."""

from __future__ import annotations

import functools
import hashlib
import json
from pathlib import Path

import pytest

FOLDER = Path(__file__).resolve().parent / "upstream"
ROOT = FOLDER.parents[1]
MANIFEST = json.loads((FOLDER / "MANIFEST.json").read_text(encoding="utf-8"))


@functools.cache
def document(name: str) -> str:
    """The document's text with whitespace collapsed; skips the test if it is not fetched."""
    path = FOLDER / name
    if not path.is_file():
        pytest.skip(f"{name} not fetched: run scripts/fetch_upstream.py")
    body = path.read_bytes()
    assert hashlib.sha256(body).hexdigest() == MANIFEST[name]["sha256"], f"{name} changed"
    return " ".join(body.decode("utf-8").split())


def says(name: str, sentence: str) -> None:
    """Fail unless the document contains the sentence (whitespace collapsed)."""
    assert " ".join(sentence.split()) in document(name), sentence


def our_docs() -> str:
    """README and GUIDE together, whitespace collapsed."""
    texts = [(ROOT / name).read_text(encoding="utf-8") for name in ("README.md", "GUIDE.md")]
    return " ".join(" ".join(texts).split())
