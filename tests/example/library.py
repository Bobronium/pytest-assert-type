from collections.abc import Callable
from dataclasses import dataclass
from typing import Generic
from typing import Literal
from typing import Protocol
from typing import TypeVar
from typing import overload

from typing_extensions import TypedDict

T = TypeVar("T")
U = TypeVar("U")


@dataclass(frozen=True)
class Box(Generic[T]):
    value: T

    def map(self, f: Callable[[T], U]) -> "Box[U]":
        return Box(f(self.value))


@overload
def parse_number(text: str, *, base10: Literal[True] = True) -> int: ...
@overload
def parse_number(text: str, *, base10: Literal[False]) -> float: ...
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
