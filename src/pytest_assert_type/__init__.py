from typing import TypeVar, TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    T = TypeVar("T")

    def check(fn: T) -> T: ...
else:
    check = pytest.mark.typecheck
