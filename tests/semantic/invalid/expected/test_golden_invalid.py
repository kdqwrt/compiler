import pytest
from pathlib import Path

from tests.semantic.helpers import analyze_file, assert_golden

# Правильные пути
INVALID_DIR = Path("tests/semantic/invalid/samples")
EXPECTED_DIR = Path("tests/semantic/invalid/expected")


@pytest.mark.parametrize("src_file", [
    "argument_count.src",
    "duplicate_declaration.src",
    "function_scope_redeclare_param.src",
    "invalid_condition.src",
    "invalid_increment.src",
    "invalid_return.src",
    "invalid_struct_field.src",
    "type_mismatch.src",
    "undeclared_variable.src",
])
def test_golden_invalid(src_file):
    """Golden-тесты для некорректных программ"""
    src_path = INVALID_DIR / src_file
    expected_path = EXPECTED_DIR / src_file.replace(".src", ".expected")

    result = analyze_file(str(src_path))

    assert result["lex_errors"] == []
    assert result["parse_errors"] == []
    assert len(result["semantic_errors"]) > 0

    assert_golden(result, expected_path)