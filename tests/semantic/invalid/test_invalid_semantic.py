from pathlib import Path

from tests.semantic.helpers import analyze_file


INVALID_DIR = Path("tests/semantic/invalid/samples")


def get_error_messages(result):
    return [e.message for e in result["semantic_errors"]]


def test_undeclared_variable():
    result = analyze_file(str(INVALID_DIR / "undeclared_variable.src"))
    assert result["lex_errors"] == []
    assert result["parse_errors"] == []
    assert len(result["semantic_errors"]) >= 1
    assert any("undeclared identifier" in msg for msg in get_error_messages(result))


def test_duplicate_declaration():
    result = analyze_file(str(INVALID_DIR / "duplicate_declaration.src"))
    assert result["lex_errors"] == []
    assert result["parse_errors"] == []
    assert len(result["semantic_errors"]) >= 1
    assert any("duplicate declaration" in msg for msg in get_error_messages(result))


def test_type_mismatch():
    result = analyze_file(str(INVALID_DIR / "type_mismatch.src"))
    assert result["lex_errors"] == []
    assert result["parse_errors"] == []
    assert len(result["semantic_errors"]) >= 1
    assert any("type mismatch" in msg for msg in get_error_messages(result))


def test_argument_count_mismatch():
    result = analyze_file(str(INVALID_DIR / "argument_count.src"))
    assert result["lex_errors"] == []
    assert result["parse_errors"] == []
    assert len(result["semantic_errors"]) >= 1
    assert any("argument count mismatch" in msg for msg in get_error_messages(result))


def test_invalid_condition():
    result = analyze_file(str(INVALID_DIR / "invalid_condition.src"))
    assert result["lex_errors"] == []
    assert result["parse_errors"] == []
    assert len(result["semantic_errors"]) >= 1
    assert any("condition must have type bool" in msg for msg in get_error_messages(result))


def test_invalid_return():
    result = analyze_file(str(INVALID_DIR / "invalid_return.src"))
    assert result["lex_errors"] == []
    assert result["parse_errors"] == []
    assert len(result["semantic_errors"]) >= 1
    assert any("return" in msg for msg in get_error_messages(result))


def test_invalid_struct_field():
    result = analyze_file(str(INVALID_DIR / "invalid_struct_field.src"))
    assert result["lex_errors"] == []
    assert result["parse_errors"] == []
    assert len(result["semantic_errors"]) >= 1
    assert any("cannot have type void" in msg for msg in get_error_messages(result))


def test_function_scope_redeclare_param():
    result = analyze_file(str(INVALID_DIR / "function_scope_redeclare_param.src"))
    assert result["lex_errors"] == []
    assert result["parse_errors"] == []
    assert len(result["semantic_errors"]) >= 1
    assert any("duplicate declaration" in msg for msg in get_error_messages(result))


def test_invalid_increment():
    result = analyze_file(str(INVALID_DIR / "invalid_increment.src"))
    assert result["lex_errors"] == []
    assert result["parse_errors"] == []
    assert len(result["semantic_errors"]) >= 1
    assert any("requires numeric operand" in msg for msg in get_error_messages(result))