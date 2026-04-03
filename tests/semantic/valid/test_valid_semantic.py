from pathlib import Path

from tests.semantic.helpers import analyze_file


VALID_DIR = Path("tests/semantic/valid/samples")


def test_valid_basic_program():
    result = analyze_file(str(VALID_DIR / "valid_basic.src"))
    assert result["lex_errors"] == []
    assert result["parse_errors"] == []
    assert result["semantic_errors"] == []


def test_valid_functions_program():
    result = analyze_file(str(VALID_DIR / "valid_functions.src"))
    assert result["lex_errors"] == []
    assert result["parse_errors"] == []
    assert result["semantic_errors"] == []


def test_valid_structs_program():
    result = analyze_file(str(VALID_DIR / "valid_structs.src"))
    assert result["lex_errors"] == []
    assert result["parse_errors"] == []
    assert result["semantic_errors"] == []


def test_valid_scopes_program():
    result = analyze_file(str(VALID_DIR / "valid_scopes.src"))
    assert result["lex_errors"] == []
    assert result["parse_errors"] == []
    assert result["semantic_errors"] == []