"""Aliased dictionary namespaces preserve linear keyword copying."""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType

import pytest

from calltimeout import run


@pytest.mark.parametrize("size", [64, 256])
@pytest.mark.parametrize("timeout", [0, 5])
@pytest.mark.parametrize("proxy_depth", [0, 1, 3])
@pytest.mark.parametrize("instance_attribute", [False, True])
def test_aliased_namespace_copies_stored_pairs_without_key_lookups(
    size: int, timeout: int, proxy_depth: int, instance_attribute: bool
) -> None:
    comparisons = 0
    hashes = 0

    class Key(str):
        def __hash__(self) -> int:
            nonlocal hashes
            hashes += 1
            return 1

        def __eq__(self, other: object) -> bool:
            nonlocal comparisons
            comparisons += 1
            return str.__eq__(self, other)

    class Parent(dict[str, object]):
        pass

    class Child(Parent):
        __dict__ = Parent.__dict__["__dict__"]

    marker = object()
    source = Child((Key(f"k{i}"), marker) for i in range(size))
    if instance_attribute:
        vars(source)["unrelated"] = marker
    original = [(id(key), id(value)) for key, value in dict.items(source)]
    values: Mapping[str, object] = source
    for _ in range(proxy_depth):
        values = MappingProxyType(values)
    called: list[bool] = []

    def capture(**keywords: object) -> dict[str, object]:
        called.append(True)
        return keywords

    comparisons = hashes = 0
    result = run(capture, timeout, kwargs=values, default=None)
    assert comparisons == 0
    assert hashes == 0
    assert called == ([True] if timeout else [])
    if timeout:
        assert result is not None
        assert list(result) == [f"k{i}" for i in range(size)]
        assert all(type(key) is str and value is marker for key, value in result.items())
    else:
        assert result is None
    assert [(id(key), id(value)) for key, value in dict.items(source)] == original
