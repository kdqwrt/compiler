from pathlib import Path
import os

from src.lexer.scanner import Scanner
from src.parser.parser import Parser
from src.semantic.analyzer import SemanticAnalyzer


def analyze_source(source: str, file_name: str = "<test>"):
    scanner = Scanner(source)
    tokens = scanner.scan_tokens()
    lex_errors = scanner.get_errors()

    parser = Parser(tokens)
    ast = parser.parse()
    parse_errors = parser.get_errors()

    analyzer = SemanticAnalyzer(file_name)
    if not lex_errors and not parse_errors:
        analyzer.analyze(ast)

    semantic_errors = analyzer.get_errors()

    return {
        "tokens": tokens,
        "ast": ast,
        "lex_errors": lex_errors,
        "parse_errors": parse_errors,
        "semantic_errors": semantic_errors,
        "symbol_table": analyzer.get_symbol_table(),
        "analyzer": analyzer,
    }


def analyze_file(path: str):
    source = Path(path).read_text(encoding="utf-8")
    return analyze_source(source, path)


def get_golden_output(result, include_symbols=True, include_types=True, include_errors=True):
    """Формирует вывод для golden-теста в формате --show-report"""
    output_parts = []

    # Если есть ошибки
    if result["semantic_errors"]:
        for error in result["semantic_errors"]:
            output_parts.append(error.format())
        return "\n".join(output_parts)

    # Если нет ошибок - используем format_validation_report()
    if result["analyzer"]:
        # Получаем полный отчет
        report = result["analyzer"].format_validation_report()
        output_parts.append("Semantic check passed successfully.\n")
        output_parts.append(report)

    return "\n".join(output_parts)


def should_update_golden():
    """Проверяет, нужно ли обновить golden-файлы"""
    return os.environ.get("UPDATE_GOLDEN", "").lower() in ("1", "true", "yes")


def assert_golden(result, expected_path: Path):
    """Сравнивает результат с ожидаемым файлом"""
    actual = get_golden_output(result)

    if should_update_golden():
        expected_path.parent.mkdir(parents=True, exist_ok=True)
        expected_path.write_text(actual, encoding="utf-8")
        print(f"Updated: {expected_path}")
        return True

    if not expected_path.exists():
        raise AssertionError(
            f"Expected file not found: {expected_path}\n"
            f"Run with: UPDATE_GOLDEN=1 pytest tests/semantic/test_golden_valid.py"
        )

    expected = expected_path.read_text(encoding="utf-8")
    assert actual == expected, f"Golden output mismatch for {expected_path}"