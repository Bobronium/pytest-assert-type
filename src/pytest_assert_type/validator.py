# SPDX-License-Identifier: MIT
from __future__ import annotations

import builtins
import dataclasses
import operator
import types
import typing
from functools import reduce
from typing import Any
from typing import TypeVar
from typing import get_args
from typing import get_origin


class ValidationError(Exception):
    """Raised when a value does not conform to the expected type."""

    def __init__(self, expected_title: str, actual_title: str) -> None:
        self.title = expected_title
        self.actual = actual_title
        super().__init__(f"Expected value of type `{expected_title}`, got `{actual_title}`")


TypeVarT = TypeVar("TypeVarT")


# ----------------------------- Pretty printing ----------------------------- #


def _pretty_type(type_spec: Any) -> str:  # noqa: PLR0911, PLR0912
    """Render a stable, compact representation of a typing spec for error messages."""
    # Treat GenericAlias specially: it represents e.g. dict[str, int], list[int] on 3.10
    # typing.NewType objects are callables with a __supertype__ and __name__
    if hasattr(type_spec, "__supertype__") and hasattr(type_spec, "__name__"):
        # Prefer the declared alias name for stable, human-friendly output
        return typing.cast("str", type_spec.__name__)
    if isinstance(type_spec, types.GenericAlias):
        origin, args = _origin_and_args(type_spec)
        # Builtin containers
        if origin in (list, tuple, dict, set, frozenset):
            if origin is tuple and len(args) == 2 and args[1] is Ellipsis:  # noqa: PLR2004
                return f"tuple[{_pretty_type(args[0])},...]"
            if origin in (list, set, frozenset) and len(args) == 1:
                return f"{origin.__name__}[{_pretty_type(args[0])}]"
            if origin is dict and len(args) == 2:  # noqa: PLR2004
                return f"dict[{_pretty_type(args[0])},{_pretty_type(args[1])}]"
            if origin is tuple:
                return f"tuple[{','.join(_pretty_type(a) for a in args)}]"
        # Fallback: generic alias for a user class like Box[int]
        if origin is not None and hasattr(origin, "__name__"):
            return f"{origin.__name__}[{','.join(_pretty_type(a) for a in args)}]"
        # Last resort
        return repr(type_spec)

    if isinstance(type_spec, type):
        return type_spec.__name__

    origin, args = _origin_and_args(type_spec)

    # Unions (A | B) or typing.Union  # noqa: ERA001
    if origin is types.UnionType or origin is typing.Union:
        return " | ".join(_pretty_type(argument) for argument in args)

    # Literal
    if origin in (typing.Literal, getattr(typing, "Literal", None)):
        return f"Literal[{','.join(repr(argument) for argument in args)}]"

    # Builtin containers
    if origin in (list, tuple, dict, set, frozenset):
        if origin is tuple and len(args) == 2 and args[1] is Ellipsis:  # noqa: PLR2004
            return f"tuple[{_pretty_type(args[0])},...]"
        if origin in (list, set, frozenset) and len(args) == 1:
            return f"{origin.__name__}[{_pretty_type(args[0])}]"
        if origin is dict and len(args) == 2:  # noqa: PLR2004
            return f"dict[{_pretty_type(args[0])},{_pretty_type(args[1])}]"
        if origin is tuple:
            return f"tuple[{','.join(_pretty_type(a) for a in args)}]"

    # Parametrized user generics, e.g., Box[int]
    if origin is not None and hasattr(origin, "__name__") and args:
        return f"{origin.__name__}[{','.join(_pretty_type(a) for a in args)}]"

    # TypedDict: print by name
    if _is_typed_dict_class(type_spec):
        return getattr(type_spec, "__name__", "TypedDict")

    return repr(type_spec)


# ----------------------------- Introspection helpers ----------------------------- #


def _is_union(type_spec: Any) -> bool:
    origin = get_origin(type_spec)
    return origin is types.UnionType or origin is typing.Union


def _is_literal(type_spec: Any) -> bool:
    return get_origin(type_spec) in (typing.Literal, getattr(typing, "Literal", None))


def _is_typed_dict_class(type_spec: Any) -> bool:
    return (
        isinstance(type_spec, type)
        and hasattr(type_spec, "__annotations__")
        and hasattr(type_spec, "__total__")
        and hasattr(type_spec, "__required_keys__")
    )


def _bind_type_variables_for_generic(
    generic_class: type[Any],
    parameters: tuple[Any, ...],
) -> dict[TypeVar, Any]:
    """Map declared TypeVars in a generic class to the concrete parameters (e.g., T -> int)."""
    declared = getattr(generic_class, "__parameters__", None)
    if not declared:
        return {}

    return {type_var: concrete for type_var, concrete in zip(declared, parameters, strict=False)}


def _substitute_type_variables(type_spec: Any, mapping: dict[TypeVar, Any]) -> Any:  # noqa: PLR0911
    """Recursively substitute TypeVars in a type spec using the provided mapping."""
    if isinstance(type_spec, TypeVar):
        return mapping.get(type_spec, type_spec)

    origin = get_origin(type_spec)
    args = get_args(type_spec)
    if not args:
        return type_spec

    if _is_union(type_spec):
        return reduce(operator.or_, (_substitute_type_variables(a, mapping) for a in args))

    if _is_literal(type_spec):
        return typing.Literal[tuple(_substitute_type_variables(a, mapping) for a in args)]

    if origin in (list, set, frozenset, dict, tuple) and args:
        substituted_args = tuple(_substitute_type_variables(a, mapping) for a in args)
        return origin[substituted_args]  # type: ignore[reportInvalidTypeArguments,unused-ignore]

    if origin is not None:
        substituted_args = tuple(_substitute_type_variables(a, mapping) for a in args)
        return origin[substituted_args]  # type: ignore[reportInvalidTypeArguments,unused-ignore]

    return type_spec


# ----------------------------- Type inference from values ----------------------------- #


def _unionize(types_list: list[Any]) -> Any:
    """Return a single type spec that is the union (or the unique element) of the given list."""
    if not types_list:
        return Any
    # Deduplicate by normalized pretty string to keep stable, compact output ordering
    unique_by_text: dict[str, Any] = {}
    for t in types_list:
        unique_by_text.setdefault(_pretty_type(t), t)
    unique_types = list(unique_by_text.values())
    if len(unique_types) == 1:
        return unique_types[0]
    # Construct a PEP 604 union for nicer printing order
    result = unique_types[0]
    for t in unique_types[1:]:
        result = result | t
    return result


def _origin_and_args(type_spec: Any) -> tuple[Any | None, tuple[Any, ...]]:
    """
    Robustly extract (origin, args) for both typing objects and PEP 585 GenericAlias on 3.10.
    Prefer __origin__/__args__ when present; fall back to typing.get_origin/get_args.
    """
    origin = getattr(type_spec, "__origin__", None)
    args = getattr(type_spec, "__args__", None)
    if origin is not None or args is not None:
        # Normalize args to a tuple
        return origin, tuple(args or ())
    # Fallback to typing helpers
    return get_origin(type_spec), tuple(get_args(type_spec) or ())


def _infer_type_spec_from_value(value: Any) -> Any:  # noqa: PLR0911, PLR0912
    """Build a typing-style spec that describes the runtime shape of 'value'."""
    # Primitives and classes
    if isinstance(value, bool):
        # Keep bool distinct from int
        return bool
    if isinstance(value, (int, float, str, bytes)):
        return type(value)

    # Containers
    if isinstance(value, list):
        element_types = [_infer_type_spec_from_value(item) for item in value]
        return list[_unionize(element_types)]  # type: ignore[misc]

    if isinstance(value, set):
        element_types = [_infer_type_spec_from_value(item) for item in value]
        return set[_unionize(element_types)]  # type: ignore[misc]

    if isinstance(value, frozenset):
        element_types = [_infer_type_spec_from_value(item) for item in value]
        return frozenset[_unionize(element_types)]  # type: ignore[misc]

    if isinstance(value, dict):
        if value:
            key_types = [_infer_type_spec_from_value(k) for k in value]
            val_types = [_infer_type_spec_from_value(v) for v in value.values()]
            return dict[_unionize(key_types), _unionize(val_types)]  # type: ignore[misc]
        return dict[Any, Any]

    if isinstance(value, tuple):
        # Represent exact arity tuples. If all elements share the same type, we could consider
        # tuple[T, ...], but using exact tuple[...] keeps more information.
        element_types = tuple(_infer_type_spec_from_value(item) for item in value)  # type: ignore[assignment]
        return tuple[element_types]  # type: ignore[valid-type]

    # Dataclasses (possibly generic)
    if dataclasses.is_dataclass(value):
        cls = value if isinstance(value, type) else type(value)
        # Try to infer generic args by reading field annotations that reference TypeVars
        parameters: tuple[Any, ...] = getattr(cls, "__parameters__", ()) or ()
        if parameters:
            type_hints = typing.get_type_hints(cls, include_extras=True)
            inferred_mapping: dict[TypeVar, Any] = {}
            for field in dataclasses.fields(cls):
                annotated = type_hints.get(field.name)
                if annotated is None:
                    continue
                # If a field annotation is itself a TypeVar, bind from value
                if isinstance(annotated, TypeVar):
                    inferred_mapping.setdefault(
                        annotated, _infer_type_spec_from_value(getattr(value, field.name))
                    )
            if inferred_mapping and all(tv in inferred_mapping for tv in parameters):
                args = tuple(inferred_mapping[tv] for tv in parameters)
                try:
                    return cls[args]  # type: ignore[index]
                except TypeError:
                    pass
        # Fall back to the class name without parameters
        return cls

    # Fallback: return the concrete class
    return type(value)


# ----------------------------- Core predicate matcher ----------------------------- #


def _matches(value: Any, expected_type: Any) -> bool:  # noqa: PLR0911, PLR0912
    """Return True if 'value' conforms to 'expected_type' (Python 3.10+ typing forms)."""
    if expected_type is Any:
        return True

    while hasattr(expected_type, "__supertype__"):
        expected_type = expected_type.__supertype__

    # Plain classes (including dataclasses without parameters)
    if isinstance(expected_type, type) and get_origin(expected_type) is None:
        if dataclasses.is_dataclass(expected_type):
            return isinstance(value, expected_type) and _matches_dataclass_fields(
                instance=value,
                dataclass_type=expected_type,
                bound_type_vars={},
            )
        if _is_typed_dict_class(expected_type):
            if not isinstance(value, dict):
                return False
            annotations: dict[str, Any] = getattr(expected_type, "__annotations__", {})
            required_keys = set(getattr(expected_type, "__required_keys__", set()))
            if not required_keys.issubset(value.keys()):
                return False
            if set(value.keys()) - set(annotations.keys()):
                return False
            for key, field_type in annotations.items():
                if key in value and not _matches(value[key], field_type):
                    return False
                if key not in value and key in required_keys:
                    return False
            return True

        return isinstance(value, expected_type)

    origin = get_origin(expected_type)
    args = get_args(expected_type)

    # Unions: match any branch
    if _is_union(expected_type):
        return any(_matches(value, option) for option in args)

    # Literal: exact value match against any of the literal options
    if _is_literal(expected_type):
        return any(value == literal_value for literal_value in args)

    # Builtin containers and tuples (precise value patterns; no captures)
    match origin, args:
        case builtins.list, [element_type]:
            return isinstance(value, list) and all(_matches(item, element_type) for item in value)

        case builtins.set, [element_type]:
            return isinstance(value, set) and all(_matches(item, element_type) for item in value)

        case builtins.frozenset, [element_type]:
            return isinstance(value, frozenset) and all(
                _matches(item, element_type) for item in value
            )

        case builtins.dict, [key_type, value_type]:
            return isinstance(value, dict) and all(
                _matches(key, key_type) and _matches(val, value_type) for key, val in value.items()
            )

        case builtins.tuple, [only_type, builtins.Ellipsis]:
            return isinstance(value, tuple) and all(_matches(item, only_type) for item in value)

        case builtins.tuple, element_types if (
            isinstance(element_types, tuple) and len(element_types) > 0
        ):
            return (
                isinstance(value, tuple)
                and len(value) == len(element_types)
                and all(
                    _matches(item, elem_type)
                    for item, elem_type in zip(value, element_types, strict=False)
                )
            )

    # Parametrized user generics (e.g., Box[int])
    if origin is not None and isinstance(origin, type):
        if not isinstance(value, origin):
            return False
        if dataclasses.is_dataclass(origin):
            bound = _bind_type_variables_for_generic(origin, args)  # type: ignore[arg-type]
            return _matches_dataclass_fields(value, origin, bound)  # type: ignore[arg-type]
        return True

    # Fallback: if origin is a real class-like alias, do a basic isinstance check
    if origin is not None and isinstance(origin, type):
        return isinstance(value, origin)

    # Unknown shape: do not silently accept
    return False


def _matches_dataclass_fields(
    instance: Any,
    dataclass_type: type[Any],
    bound_type_vars: dict[TypeVar, Any],
) -> bool:
    """Validate dataclass fields against the (possibly typevar-substituted) annotations."""
    type_hints = typing.get_type_hints(dataclass_type, include_extras=True)
    for field in dataclasses.fields(dataclass_type):
        if field.name not in type_hints:
            continue
        annotated_field_type = type_hints[field.name]
        concrete_field_type = (
            _substitute_type_variables(annotated_field_type, bound_type_vars)
            if bound_type_vars
            else annotated_field_type
        )
        if not _matches(getattr(instance, field.name), concrete_field_type):
            return False
    return True


# ----------------------------- Public API ----------------------------- #


def validate(value: Any, expected_type: Any) -> None:
    """
    Raise ValidationError with the OUTER expected type and the ACTUAL inferred type shape
    if the value does not match the expected specification.
    """
    expected_title = _pretty_type(expected_type)
    if not _matches(value, expected_type):
        actual_spec = _infer_type_spec_from_value(value)
        actual_title = _pretty_type(actual_spec)
        raise ValidationError(expected_title, actual_title)
