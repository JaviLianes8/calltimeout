"""Stored keyword copying preserves custom mapping lookup and validation semantics."""

from __future__ import annotations

from collections import UserDict
from collections.abc import Mapping
from types import MappingProxyType
from typing import Any

import pytest

from calltimeout import run


class CustomValues(dict[str, int]):
    def __getitem__(self, key: str) -> int:
        return super().__getitem__(key) + 10


class CustomKeys(dict[str, int]):
    def keys(self) -> Any:
        return {"selected": 0}.keys()


class CustomAttributes(dict[str, int]):
    def __getattribute__(self, name: str) -> Any:
        if name == "keys":
            return lambda: ["selected"]
        return super().__getattribute__(name)


class UnusedItems(dict[str, int]):
    def items(self) -> Any:
        raise AssertionError("items override is not part of keyword mapping reads")


@pytest.mark.parametrize("proxy_depth", [0, 1, 2])
@pytest.mark.parametrize(
    ("mapping_type", "expected"),
    [
        (CustomValues, {"selected": 11, "other": 12}),
        (CustomKeys, {"selected": 1}),
        (CustomAttributes, {"selected": 1}),
        (UnusedItems, {"selected": 1, "other": 2}),
        (UserDict, {"selected": 1, "other": 2}),
    ],
)
def test_custom_mapping_hooks_are_preserved(
    proxy_depth: int, mapping_type: Any, expected: dict[str, int]
) -> None:
    values: Mapping[str, int] = mapping_type(selected=1, other=2)
    for _ in range(proxy_depth):
        values = MappingProxyType(values)
    assert run(lambda **kw: kw, 5, kwargs=values) == expected


@pytest.mark.parametrize("proxy_depth", [0, 1, 2])
@pytest.mark.parametrize("hidden_namespace", [False, True])
def test_instance_keys_override_is_preserved(proxy_depth: int, hidden_namespace: bool) -> None:
    class Keywords(dict[str, int]):
        pass

    mapping_type = (
        type("HiddenNamespace", (Keywords,), {"__dict__": property(lambda self: {})})
        if hidden_namespace
        else Keywords
    )
    source = mapping_type(selected=1, other=2)
    source.keys = lambda: {"selected": 0}.keys()
    values: Mapping[str, int] = source
    for _ in range(proxy_depth):
        values = MappingProxyType(values)
    assert run(lambda **kw: kw, 5, kwargs=values) == {"selected": 1}


@pytest.mark.parametrize("proxy_depth", [0, 1, 2])
def test_aliased_namespace_preserves_instance_keys_selection(proxy_depth: int) -> None:
    class Parent(dict[str, int]):
        pass

    class Child(Parent):
        __dict__ = Parent.__dict__["__dict__"]

    source = Child(selected=1, other=2)
    vars(source)["keys"] = lambda: ["selected"]
    values: Mapping[str, int] = source
    for _ in range(proxy_depth):
        values = MappingProxyType(values)
    assert run(lambda **kw: kw, 5, kwargs=values) == {"selected": 1}
    assert list(dict.items(source)) == [("selected", 1), ("other", 2)]


@pytest.mark.parametrize("proxy_depth", [0, 1, 2])
def test_invalid_key_is_rejected_before_custom_value_lookup(proxy_depth: int) -> None:
    reads: list[object] = []

    class InvalidKeys(dict[Any, int]):
        def __getitem__(self, key: object) -> int:
            reads.append(key)
            raise AssertionError("invalid key must not be looked up")

    values: Mapping[Any, int] = InvalidKeys({1: 2})
    for _ in range(proxy_depth):
        values = MappingProxyType(values)
    with pytest.raises(TypeError, match="kwargs keys must be strings"):
        run(str, 0, kwargs=values, default="fallback")
    assert reads == []


@pytest.mark.parametrize("proxy_depth", [0, 1, 2])
def test_inherited_dictionary_wrappers_do_not_rehash_keys(proxy_depth: int) -> None:
    class Key(str):
        def __hash__(self) -> int:
            if forbid_hashing:
                raise AssertionError("stored keys must not be hashed again")
            return 1

    class Parent(dict[str, object]):
        pass

    class Keywords(Parent):
        pass

    forbid_hashing = False
    marker = object()
    source = Keywords({Key(f"k{i}"): marker for i in range(50)})
    original = [(id(key), id(value)) for key, value in source.items()]
    values: Mapping[str, object] = source
    for _ in range(proxy_depth):
        values = MappingProxyType(values)
    forbid_hashing = True
    result = run(lambda **kw: kw, 5, kwargs=values)
    assert list(result) == [f"k{i}" for i in range(50)]
    assert all(type(key) is str and value is marker for key, value in result.items())
    assert [(id(key), id(value)) for key, value in source.items()] == original


@pytest.mark.parametrize("proxy_depth", [0, 1, 2])
def test_hidden_class_namespace_preserves_custom_lookup(proxy_depth: int) -> None:
    metaclass = type("HiddenNamespace", (type,), {"__dict__": property(lambda cls: {})})
    keywords = metaclass(
        "Keywords", (dict,), {"__getitem__": lambda self, key: dict.__getitem__(self, key) + 10}
    )
    values: Mapping[str, int] = keywords(value=1)
    for _ in range(proxy_depth):
        values = MappingProxyType(values)
    assert run(lambda **kw: kw, 5, kwargs=values) == {"value": 11}
