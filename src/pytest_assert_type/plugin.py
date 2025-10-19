# SPDX-FileCopyrightText: 2023-present Arseny Boykov (Bobronium) <mail@bobronium.me>
#
# SPDX-License-Identifier: MIT

from __future__ import annotations

import ast
from typing import TYPE_CHECKING
from typing import Any
from typing import Never
from typing import NoReturn
from typing import TypeVar
from typing import _TypedDictMeta  #  type: ignore[attr-defined]
from typing import cast

import _pytest.assertion.rewrite
import pytest
import typing_extensions
from _pytest.assertion.rewrite import AssertionRewriter
from pydantic import PydanticUserError

from pytest_assert_type import subtests_pycharm_patch

__all__ = ["assert_type"]


T = TypeVar("T")

if TYPE_CHECKING:
    from collections.abc import Callable

    from typing_extensions import assert_type
else:

    def assert_type(val: T, typ: type[T] = typing_extensions.Never, /) -> None:
        __tracebackhide__ = True

        if typ in {
            Never,
            NoReturn,
            typing_extensions.Never,
            typing_extensions.NoReturn,
        }:  # pragma: no cover
            # if we end up here, it means code that must have produced error, did not
            # so, we shall not interfere
            return

        from pydantic import ConfigDict
        from pydantic import TypeAdapter
        from pydantic import ValidationError

        if issubclass(type(typ), _TypedDictMeta | typing_extensions._TypedDictMeta):  # noqa: SLF001
            config = None
        else:
            config = ConfigDict(strict=True, arbitrary_types_allowed=True)
        try:
            TypeAdapter(typ, config=config).validate_python(val)
        except ValidationError as e:
            raise AssertionError(f"Expected value of type `{e.title}`, got `{val}`") from None
        except PydanticUserError as e:  # pragma: no cover
            raise TypeError(e) from None


@pytest.fixture
def assert_type_fixture() -> Callable[[Any, Any], None]:
    return assert_type  # type: ignore[return-value,unused-ignore]


class AssertTypeToSubtest(AssertionRewriter):
    def run(self, mod: ast.Module) -> None:
        nodes = list(mod.body)
        while nodes:
            match nodes.pop():
                case ast.FunctionDef() as function_definition:
                    self.maybe_rewrite_assert_type(function_definition)
                case ast.ClassDef(body=body):
                    nodes.extend(body)
        super().run(mod)

    def maybe_rewrite_assert_type(self, func_def: ast.FunctionDef) -> None:
        if not func_def.name.startswith("test_"):
            return
        for decorator in func_def.decorator_list:
            match decorator:
                case ast.Attribute(
                    attr="check" | "typecheck",
                    value=(
                        ast.Name("pytest_assert_type")
                        | ast.Attribute(attr="mark", value=ast.Name("pytest"))
                    ),
                ):
                    break

        else:
            return

        arg_names = {a.arg for a in func_def.args.args}
        if "subtests" not in arg_names:
            func_def.args.args.append(ast.arg(arg="subtests", annotation=None))
        if "assert_type_fixture" not in arg_names:
            func_def.args.args.append(ast.arg(arg="assert_type_fixture", annotation=None))

        ast.fix_missing_locations(func_def.args)

        self._process_statements(func_def.body, pytest_raises=None)
        return

    def _process_statements(self, body: list[ast.stmt], pytest_raises: ast.With | None) -> None:
        for i, stmt in enumerate(body):
            match stmt:
                case ast.Expr(  # pragma: no cover (cov says pattern never matches ?)
                    value=ast.Call(func=ast.Name(id="assert_type" | "assert_never")) as call
                ):
                    body[i] = self._maybe_wrap(stmt, call, pytest_raises)
                case ast.With(body=new_body) if self._is_pytest_raises(stmt):
                    assert len(new_body) == 1, (
                        "pytest.raises() with multiple statements is ambiguous."
                        " Rewrite with at most one statement"
                    )
                    self._process_statements(new_body, pytest_raises=stmt)
                case ast.AST(body=new_body):  # type: ignore[attr-defined,misc,unused-ignore]
                    self._process_statements(new_body, pytest_raises)

    def _is_pytest_raises(self, with_node: ast.With) -> bool:
        for item in with_node.items:
            match item.context_expr:
                case ast.Call(
                    func=ast.Attribute(value=ast.Name(id="pytest"), attr="raises"),
                ):
                    return True
                case _:  # pragma: no cover
                    pass
        return False

    def _maybe_wrap(
        self, stmt: ast.stmt, call: ast.Call, pytest_raises: ast.With | None
    ) -> ast.stmt:
        assert_function_name = cast("ast.Name", call.func)
        match pytest_raises, assert_function_name.id, call.args:
            case (None, "assert_never", [expression]):
                return self._skip_statement("assert_never(...)", stmt)
            case (
                None,
                "assert_type",
                [
                    expression,
                    (
                        ast.Name("NoReturn" | "Never" as name)
                        | ast.Attribute(
                            value="typing" | "typing_extensions", attr="NoReturn" | "Never" as name
                        )
                    ),
                ],
            ):
                return self._skip_statement(f"assert_type(..., {name})", stmt)

            case [_, _, [expression, *_]]:  # pragma: no cover
                pass
            case _:
                raise NotImplementedError(
                    "Expected assert_type or assert_never to have one argument"
                )

        assert_function_name.id = "assert_type_fixture"
        label = ast.unparse(expression)
        label = " ".join(label.split())

        with_item = ast.withitem(
            context_expr=ast.Call(
                func=ast.Attribute(
                    value=ast.Name(id="subtests", ctx=ast.Load()),
                    attr="test",
                    ctx=ast.Load(),
                ),
                args=[ast.Constant(value=label)],
                keywords=[],
            ),
            optional_vars=None,
        )
        if pytest_raises:
            assert len(pytest_raises.body) == 1, (
                "pytest.raises() with multiple statements is ambiguous."
                " Rewrite with at most one statement"
            )
            assert pytest_raises.body == [stmt], (
                "Unexpected statement in pytest.raises(). Looks like a bug."
            )
            # swapping pytest.raises() and subtests.test()
            context_manager = ast.With(pytest_raises.items, body=[stmt], type_comment=None)
            ast.copy_location(context_manager, pytest_raises)
            ast.fix_missing_locations(with_item)
            pytest_raises.items = [with_item]
            pytest_raises.body = [context_manager]
        else:
            context_manager = ast.With(items=[with_item], body=[stmt], type_comment=None)

        ast.copy_location(context_manager, stmt)
        ast.fix_missing_locations(context_manager)

        return context_manager

    def _skip_statement(self, expression: str, stmt: ast.stmt) -> ast.Expr:
        new_stmt = ast.Expr(
            ast.Call(
                func=ast.Attribute(
                    value=ast.Name(id="pytest", ctx=ast.Load()),
                    attr="skip",
                    ctx=ast.Load(),
                ),
                args=[ast.Constant(value=f"Not executing {expression} outside of pytest.raises()")],
                keywords=[],
            )
        )
        ast.copy_location(new_stmt, stmt)
        ast.fix_missing_locations(new_stmt)
        return new_stmt


def pytest_configure(config: Any) -> None:
    config.addinivalue_line(
        "markers", "typecheck: mark test to check assert_type statements in runtime."
    )


_pytest.assertion.rewrite.AssertionRewriter = AssertTypeToSubtest  # type: ignore[misc]

subtests_pycharm_patch.enable()
