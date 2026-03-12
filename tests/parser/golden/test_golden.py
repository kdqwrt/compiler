import pytest
import sys
from pathlib import Path

# Добавляем корневую директорию в путь
root_dir = Path(__file__).parent.parent.parent.absolute()
sys.path.insert(0, str(root_dir))

from src.lexer.scanner import Scanner
from src.parser.parser import Parser
from src.parser.ast import pretty_print

GOLDEN_DIR = Path(__file__).parent


def normalize(text: str) -> str:
    return text.replace("\r\n", "\n").strip()


def get_golden_tests():
    return sorted(GOLDEN_DIR.glob("*.src"))


@pytest.mark.parametrize("src_file", get_golden_tests(), ids=lambda p: p.stem)
def test_golden(src_file: Path):
    expected_file = src_file.with_suffix(".expected")

    assert expected_file.exists(), f"Missing expected file: {expected_file}"

    source = src_file.read_text(encoding="utf-8")

    scanner = Scanner(source)
    tokens = scanner.scan_tokens()
    lex_errors = scanner.get_errors()
    assert not lex_errors, f"Lexer errors in {src_file.name}: {lex_errors}"

    parser = Parser(tokens)
    ast = parser.parse()
    parse_errors = parser.get_errors()
    assert not parse_errors, f"Parser errors in {src_file.name}: {parse_errors}"

    actual = normalize(pretty_print(ast))
    expected = normalize(expected_file.read_text(encoding="utf-8"))

    assert actual == expected, (
        f"AST mismatch for {src_file.stem}\n\n"
        f"Expected:\n{expected}\n\n"
        f"Got:\n{actual}"
    )