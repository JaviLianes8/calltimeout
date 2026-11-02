"""Validation rejects malformed inputs without retaining their diagnostic text."""

from __future__ import annotations

import traceback
from collections.abc import Iterator, Mapping
from fractions import Fraction
from typing import Any

import pytest

from calltimeout import run, with_timeout

SECRET = "TOKEN_PRIVATE_7fb52e36"


class BadFloat(float):
    def __float__(self) -> float:
        error = RuntimeError(SECRET + "x" * 1_000_000)
        vars(error)["__notes__"] = [SECRET + "n" * 100_000]
        raise error from LookupError(SECRET)


class BadClass:
    @property  # type: ignore[misc]
    def __class__(self) -> type:
        raise LookupError(SECRET)


class BadMapping(Mapping[str, int]):
    def __init__(self, hook: str) -> None:
        self.hook = hook

    def __iter__(self) -> Iterator[str]:
        if self.hook == "iteration":
            raise LookupError(SECRET + "x" * 100_000)
        return iter(["value"])

    def __getitem__(self, key: str) -> int:
        raise LookupError(SECRET + "x" * 100_000)

    def __len__(self) -> int:
        return 1


def assert_safe(error: BaseException) -> None:
    pending = [error]
    seen: set[int] = set()
    while pending:
        current = pending.pop()
        if id(current) in seen:
            continue
        seen.add(id(current))
        text = "".join(traceback.format_exception(type(current), current, current.__traceback__))
        assert SECRET not in text
        assert len(text) < 10_000
        pending.extend(e for e in (current.__cause__, current.__context__) if e is not None)


@pytest.mark.parametrize("entry", ["run", "decorator"])
def test_negative_fraction_cannot_become_a_zero_budget(entry: str) -> None:
    timeout = Fraction(-1, 10**400)
    with pytest.raises(ValueError, match="negative"):
        if entry == "run":
            run(str, timeout, default="fallback")
        else:
            with_timeout(timeout)


@pytest.mark.parametrize("entry", ["run", "decorator"])
def test_conversion_failure_has_no_caller_text_or_retained_chain(entry: str) -> None:
    with pytest.raises(TypeError) as info:
        if entry == "run":
            run(str, BadFloat(1))
        else:
            with_timeout(BadFloat(1))
    assert_safe(info.value)


@pytest.mark.parametrize("hook", ["iteration", "lookup"])
def test_mapping_access_failure_is_a_safe_argument_error(hook: str) -> None:
    with pytest.raises(TypeError, match="kwargs") as info:
        run(str, 0, kwargs=BadMapping(hook), default="fallback")
    assert_safe(info.value)


@pytest.mark.parametrize("field", ["timeout", "args", "kwargs", "mode"])
def test_validation_uses_actual_types_without_reading_class_properties(field: str) -> None:
    options: dict[str, Any] = {"timeout": 0, field: BadClass()}
    with pytest.raises(TypeError, match=field) as info:
        run(str, **options)
    assert_safe(info.value)


@pytest.mark.parametrize("entry", ["run", "decorator"])
def test_invalid_mode_is_not_quoted(entry: str) -> None:
    mode: Any = SECRET
    with pytest.raises(ValueError, match="expected one of") as info:
        if entry == "run":
            run(str, 0, mode=mode)
        else:
            with_timeout(0, mode=mode)
    assert_safe(info.value)


class CollidingKey(str):
    comparisons = 0

    def __hash__(self) -> int:
        return 42

    def __eq__(self, other: object) -> bool:
        type(self).comparisons += 1
        return str.__eq__(self, other)

    def __str__(self) -> str:
        raise AssertionError("key conversion must use the underlying string")


class CollisionMapping(Mapping[str, int]):
    def __init__(self, size: int) -> None:
        self.size = size
        self.reads = 0

    def __iter__(self) -> Iterator[str]:
        return (CollidingKey(f"k{index}") for index in range(self.size))

    def __getitem__(self, key: str) -> int:
        self.reads += 1
        return 1

    def __len__(self) -> int:
        return self.size


@pytest.mark.parametrize("size", [500, 4000])
def test_mapping_keys_do_not_trigger_quadratic_collision_work(size: int) -> None:
    values = CollisionMapping(size)
    CollidingKey.comparisons = 0
    assert run(str, 0, kwargs=values, default="fallback") == "fallback"
    assert CollidingKey.comparisons <= size
    assert values.reads == size


def test_normalized_keys_preserve_keyword_values() -> None:
    values = CollisionMapping(20)
    assert run(lambda **kw: kw, 5, kwargs=values) == {f"k{i}": 1 for i in range(20)}
    assert values.reads == 20


@pytest.mark.parametrize("size", [500, 4000])
@pytest.mark.parametrize("timeout", [0, 5])
def test_existing_dict_keys_need_no_collision_comparisons(size: int, timeout: int) -> None:
    expected = {f"k{i}": i for i in range(size)}
    values: dict[str, int] = {CollidingKey(key): value for key, value in expected.items()}
    original = list(values.items())
    called: list[bool] = []

    def capture(**keywords: object) -> dict[str, object]:
        called.append(True)
        assert all(type(key) is str for key in keywords)
        return keywords

    CollidingKey.comparisons = 0
    result = run(capture, timeout, kwargs=values, default=None)
    assert CollidingKey.comparisons == 0
    assert result == (expected if timeout else None)
    assert called == ([True] if timeout else [])
    assert list(values.items()) == original
