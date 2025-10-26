"""
Test your typehints interface in this package:

cat > tests/typehints/test_interface.py << EOF
from typing import assert_type

import pytest_assert_type

import {{ cookiecutter.project_name }}

@pytest_assert_type.check
def test_add():
    assert_type(calculator.add(1, 2), int)
    assert_type(calculator.add(3.14, 5), float)
"""
