import pytest
from pathlib import Path

from tests.semantic.helpers import analyze_file, assert_golden

VALID_DIR = Path("tests/semantic/valid/samples")
EXPECTED_DIR = Path("tests/semantic/valid/expected")


@pytest.mark.parametrize("src_file", [
    "valid_basic.src",
    "valid_functions.src",
    "valid_structs.src",
    "valid_scopes.src",
])
def test_golden_valid(src_file):
    """Golden-тесты для корректных программ"""
    src_path = VALID_DIR / src_file
    expected_path = EXPECTED_DIR / src_file.replace(".src", ".expected")

    result = analyze_file(str(src_path))

    # Проверяем, что ошибок нет
    assert result["lex_errors"] == []
    assert result["parse_errors"] == []
    assert result["semantic_errors"] == []

    assert_golden(result, expected_path)