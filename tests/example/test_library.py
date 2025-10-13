from __future__ import annotations

from typing_extensions import assert_type

import pytest_assert_type
from tests.example.library import Box
from tests.example.library import User
from tests.example.library import first
from tests.example.library import make_user
from tests.example.library import parse_number
from tests.example.library import size


def test_generics_and_map() -> None:
    b = Box(21)
    b2 = b.map(lambda n: n * 2.0)
    assert_type(b, Box[int])
    assert_type(b2, Box[float])
    assert_type(b2.value, float)


@pytest_assert_type.check
def test_overloads() -> None:
    i = parse_number("123", base10=True)
    f = parse_number("1.5", base10=False)
    assert_type(i, int)
    assert_type(f, float)


@pytest_assert_type.check
def test_protocol_structural() -> None:
    class V:
        def __len__(self) -> int:
            return 3

    s = size("abc")
    v = size(V())
    assert_type(s, int)
    assert_type(v, int)


@pytest_assert_type.check
def test_generic_binding() -> None:
    xs = [1, 2, 3]
    head = first(xs)
    assert_type(xs, list[int])
    assert_type(head, int)


@pytest_assert_type.check
def test_deep_containers() -> None:
    u = make_user(7, "Ada")
    assert_type(u, User)
    # Reach inside the structure to show deep shape validation:
    assert_type(u["id"], int)
    assert_type(u["name"], str)
    assert_type(u["history"], list[tuple[int, str]])
    assert_type(u["history"][0], tuple[int, str])
    assert_type(u["history"][0][0], int)
    assert_type(u["history"][0][1], str)
