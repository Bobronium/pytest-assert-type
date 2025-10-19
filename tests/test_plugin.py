# SPDX-FileCopyrightText: 2023-present Arseny Boykov (Bobronium) <mail@bobronium.me>
#
# SPDX-License-Identifier: MIT

import contextlib
import re
import sys
from collections.abc import Callable
from typing import TYPE_CHECKING
from typing import Literal
from typing import NoReturn

import pytest
from pytest_subtests import SubTests
from typing_extensions import Never
from typing_extensions import assert_never
from typing_extensions import assert_type

import pytest_assert_type


class ArbitraryType: ...


@pytest_assert_type.check
def test_assert_type() -> None:  # no need to add subtests/fixture args yourself
    assert_type({"x": 1}, dict[str, int])
    assert_type({"x": ArbitraryType()}, dict[str, ArbitraryType])

    if not TYPE_CHECKING:
        with pytest.raises(
            AssertionError,
            match=re.escape("Expected value of type `dict[str,int]`, got `{'x': 'nope'}`"),
        ):
            assert_type({"x": "nope"}, dict[str, int])  # type: ignore[arg-type,type-arg,assignment]

    with pytest.raises(SystemExit):
        assert_type(sys.exit(), NoReturn)

    with pytest.raises(SystemExit):
        assert_type(sys.exit(), Never)

    with pytest.raises(SystemExit):
        assert_never(sys.exit())

    if not TYPE_CHECKING:
        assert_type(sys.exit(), NoReturn)

        assert_type(sys.exit(), Never)

        with contextlib.nullcontext():
            assert_type(sys.exit(), Never)

        assert_never(sys.exit())


def test_not_decorated() -> None:
    if not TYPE_CHECKING:
        assert_type(1, str)


@pytest_assert_type.check
def test_has_subtests(subtests: SubTests) -> None:
    with subtests.test("sub"):  # nonsensical to use like this, but smoke test anyways
        assert_type(1, Literal[1])


@pytest_assert_type.check
def test_has_assert_type_fixture(
    assert_type_fixture: Callable[[object, type[object]], None],
) -> None:
    assert_type_fixture(1, int)
    with pytest.raises(AssertionError):
        assert_type_fixture(1, str)


@pytest_assert_type.check
def test_has_both_fixtures(
    subtests: SubTests,
    assert_type_fixture: Callable[[object, type[object] | object], None],
) -> None:
    with subtests.test("sub"):
        assert_type_fixture(1, Literal[1])


@pytest.mark.skipif("False", reason="No reason at all")
def test_different_decorator() -> None:
    if not TYPE_CHECKING:
        assert_type(1, str)  # type: ignore[arg-type,type-arg,assignment]


# subtest doesn't support xfail, that's a shame...
# @pytest.mark.xfail(strict=True, raises=AssertionError)
# @pytest_assert_type.check
# def test_fail_to_raise():
#     with pytest.raises(SystemExit):
#         assert_never(...)


class Test:
    @pytest_assert_type.check
    def test_assert_type_as_method(self) -> None:
        assert_type({"x": 1}, dict[str, int])
        assert_type({"x": ArbitraryType()}, dict[str, ArbitraryType])

        if not TYPE_CHECKING:
            with pytest.raises(
                AssertionError,
                match=re.escape("Expected value of type `dict[str,int]`, got `{'x': 'nope'}`"),
            ):
                assert_type({"x": "nope"}, dict[str, int])  # type: ignore[arg-type,type-arg,assignment]

        with pytest.raises(SystemExit):
            assert_type(sys.exit(), NoReturn)

        with pytest.raises(SystemExit):
            assert_type(sys.exit(), Never)

        with pytest.raises(SystemExit):
            assert_never(sys.exit())

        if not TYPE_CHECKING:
            assert_type(sys.exit(), NoReturn)

            assert_type(sys.exit(), Never)

            with contextlib.nullcontext():
                assert_type(sys.exit(), Never)  # still skipped

            assert_type(sys.exit(), NoReturn)

        assignment: Literal[1] = 1

        assert_type(assignment, Literal[1])

    def not_a_test(self) -> None: ...

    def test_not_decorated_as_method(self) -> None:
        if not TYPE_CHECKING:
            assert_type(1, str)

    @pytest.mark.skipif("False", reason="No reason at all")
    def test_different_decorator_as_method(self) -> None:
        if not TYPE_CHECKING:
            assert_type(1, str)

    @pytest_assert_type.check
    def test_has_subtests_as_method(self, subtests: SubTests) -> None:
        with subtests.test("sub"):  # nonsensical to use like this, but smoke test anyways
            assert_type(1, Literal[1])

    @pytest_assert_type.check
    def test_has_assert_type_fixture_as_method(
        self,
        assert_type_fixture: Callable[[object, type[object]], None],
    ) -> None:
        assert_type_fixture(1, int)
        with pytest.raises(AssertionError):
            assert_type_fixture(1, str)

    @pytest_assert_type.check
    def test_has_both_fixtures_as_method(
        self,
        subtests: SubTests,
        assert_type_fixture: Callable[[object, type[object]], None],
    ) -> None:
        with subtests.test("sub"):
            assert_type_fixture(1, int)

    # subtest doesn't support xfail, that's a shame...
    # @pytest.mark.xfail(strict=True, raises=AssertionError)
    # @pytest_assert_type.check
    # def test_fail_to_raise_as_method(self):
    #     with pytest.raises(SystemExit):
    #         assert_never(...)
