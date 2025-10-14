# SPDX-FileCopyrightText: 2023-present Arseny Boykov (Bobronium) <mail@bobronium.me>
#
# SPDX-License-Identifier: MIT

from typing import TypeVar, TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    T = TypeVar("T")

    def check(fn: T) -> T: ...
else:
    check = pytest.mark.typecheck
