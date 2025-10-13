# pytest-assert-type

Type-check and runtime-validate your interfaces with `typing.assert_type()`

Each assertion is ran in a subtest, so you get report for all of them regardless of failure.

# 📦 Installation

```bash
uv add --optional dev pytest pytest_assert_type
```

# 🎼 Usage

### `cat library.py`

```python
from dataclasses import dataclass
from typing import Callable, Generic, Literal, Protocol, TypeVar, overload
from typing_extensions import TypedDict


T = TypeVar("T")
U = TypeVar("U")


@dataclass(frozen=True)
class Box(Generic[T]):
    value: T

    def map(self, f: Callable[[T], U]) -> "Box[U]":
        return Box(f(self.value))


@overload
def parse_number(text: str, *, base10: Literal[True] = True) -> int:
    ...


@overload
def parse_number(text: str, *, base10: Literal[False]) -> float:
    ...


def parse_number(text: str, *, base10: bool = True) -> int | float:
    return int(text) if base10 else float(text)


class SupportsLen(Protocol):
    def __len__(self) -> int: ...


def size(x: SupportsLen) -> int:
    return len(x)


def first(xs: list[T]) -> T:
    return xs[0]


class User(TypedDict):
    id: int
    name: str
    history: list[tuple[int, str]]


def make_user(user_id: int, name: str) -> User:
    history: list[tuple[int, str]] = [(user_id, name)]
    return {"id": user_id, "name": name, "history": history}
```

### `cat test_typehints.py`

```python
from __future__ import annotations

import pytest
import pytest_assert_type
from typing_extensions import assert_type

from library import Box, User, first, make_user, parse_number, size


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
```

### `mypy test_typehints.py`

```python
Success: no
issues
found in 1
source
file
```

### `pytest -v  test_typehints.py`

```python
== == == == == == == == == == == == == == == == == == test
session
starts == == == == == == == == == == == == == == == == == ==
platform
darwin - - Python
3.14
.0, pytest - 8.4
.2, pluggy - 1.6
.0 - -.venv / bin / python3
collected
5
items

test_library.py::test_generics_and_map
PASSED[20 %]
test_library.py::test_overloads
test_library.py::test_overloads[i][subtest]
SUBPASS[40 %]
test_library.py::test_overloads[f][subtest]
SUBPASS[60 %]
test_library.py::test_overloads
PASSED[80 %]
test_library.py::test_protocol_structural
test_library.py::test_protocol_structural[s][subtest]
SUBPASS[100 %]
test_library.py::test_protocol_structural[v][subtest]
SUBPASS[120 %]
test_library.py::test_protocol_structural
PASSED[140 %]
test_library.py::test_generic_binding
test_library.py::test_generic_binding[xs][subtest]
SUBPASS[160 %]
test_library.py::test_generic_binding[head][subtest]
SUBPASS[180 %]
test_library.py::test_generic_binding
PASSED[200 %]
test_library.py::test_deep_containers
test_library.py::test_deep_containers[u][subtest]
SUBPASS[220 %]
test_library.py::test_deep_containers[u['id']][subtest]
SUBPASS[240 %]
test_library.py::test_deep_containers[u['name']][subtest]
SUBPASS[260 %]
test_library.py::test_deep_containers[u['history']][subtest]
SUBPASS[280 %]
test_library.py::test_deep_containers[u['history'][0]][subtest]
SUBPASS[300 %]
test_library.py::test_deep_containers[u['history'][0][0]][subtest]
SUBPASS[320 %]
test_library.py::test_deep_containers[u['history'][0][1]][subtest]
SUBPASS[340 %]
test_library.py::test_deep_containers
PASSED[360 %]

== == == == == == == == == == == == == = 5
passed, 13
subtests
passed in 0.09
s == == == == == == == == == == == == == =
```

# 🚧 Development

- `brew install go-task` or [other options](https://taskfile.dev/docs/installation)
- `task -l`
    ```python
    - task: Available tasks for this project:
    * add:             Add optional dependency: `task add -- test pytest-cov`
    * clear:           Clear __pycache__
    * default:         Run all checks: `task`
    * format:          Format
    * htmlcov:         Run tests and open htmlcov in browser
    * lint:            Lint
    * remove:          Add optional dependency: `task add -- test pytest-cov`
    * setup:           Install dependencies
    * test:            Run tests
    * typecheck:       Typecheck
    ```
- Before push: `task`